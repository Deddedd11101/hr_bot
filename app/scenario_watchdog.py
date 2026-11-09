"""Conservative runtime diagnostics; never retries or completes scenario delivery."""

import hashlib
import logging
from datetime import timedelta

from sqlalchemy import update

from .models import FlowLaunchRequest, ScenarioProgress, ScenarioTemplate
from .notifications import notify_hr
from .time_utils import utc_now

logger = logging.getLogger(__name__)
ALERT_AFTER = timedelta(hours=3)


def progress_health(db, progress, *, now=None, future_job=False):
    now = now or utc_now()
    age = max(0, int((now - progress.updated_at).total_seconds()))
    continuation = db.query(FlowLaunchRequest).filter(
        FlowLaunchRequest.employee_id == progress.employee_id,
        FlowLaunchRequest.flow_key == progress.scenario_key,
        FlowLaunchRequest.processed_at.is_(None),
        FlowLaunchRequest.skip_step_key.isnot(None),
    ).order_by(FlowLaunchRequest.requested_at).first()
    result = {"idle_seconds": age, "alert_due": False, "next_at": None}
    if progress.is_completed or progress.interrupted_at:
        return {**result, "state": "closed", "reason": "Диалог завершён"}
    if progress.waiting_for_response:
        return {**result, "state": "waiting_human", "reason": "Ожидается ответ получателя; автоматического срока завершения нет"}
    if continuation and continuation.requested_at > now:
        return {**result, "state": "scheduled", "reason": "Продолжение запланировано",
                "next_at": continuation.requested_at.isoformat()}
    if future_job:
        return {**result, "state": "scheduled", "reason": "Следующий шаг ожидает времени запуска"}
    if age < ALERT_AFTER.total_seconds():
        return {**result, "state": "processing", "reason": "Выполняется шаг или ожидается проверка планировщика"}
    state = "delivery_uncertain" if progress.last_delivery_error else "stale_runtime"
    return {**result, "state": state, "alert_due": True,
            "reason": "Нет движения больше 3 часов. Доставку нужно проверить; автоматический повтор отключён"}


def _has_future_job(scheduler, progress, now):
    if scheduler is None or not hasattr(scheduler, "get_jobs"):
        return False
    for job in scheduler.get_jobs():
        args = getattr(job, "args", ())
        when = getattr(job, "next_run_time", None)
        if len(args) < 3 or args[1:3] != (progress.employee_id, progress.scenario_key) or when is None:
            continue
        from datetime import UTC
        when_utc = when.astimezone(UTC).replace(tzinfo=None) if when.tzinfo else when
        if when_utc > now:
            return True
    return False


async def check_runtime(db, messenger, scheduler=None):
    now = utc_now()
    progresses = db.query(ScenarioProgress).filter(
        ScenarioProgress.is_completed.is_(False), ScenarioProgress.interrupted_at.is_(None),
        ScenarioProgress.waiting_for_response.is_(False),
        ScenarioProgress.updated_at <= now - ALERT_AFTER,
    ).all()
    alerts = []
    for progress in progresses:
        health = progress_health(db, progress, now=now, future_job=_has_future_job(scheduler, progress, now))
        if not health["alert_due"]:
            continue
        # Claim once per unchanged runtime snapshot before any external notification.
        fingerprint = hashlib.sha256(f"{progress.started_at}:{progress.updated_at}:{health['state']}".encode()).hexdigest()
        claimed = db.execute(update(ScenarioProgress).where(
            ScenarioProgress.id == progress.id, ScenarioProgress.updated_at == progress.updated_at,
            ScenarioProgress.waiting_for_response.is_(False), ScenarioProgress.is_completed.is_(False),
            ScenarioProgress.interrupted_at.is_(None),
            (ScenarioProgress.watchdog_alert_key.is_(None) | (ScenarioProgress.watchdog_alert_key != fingerprint)),
        ).values(watchdog_alert_key=fingerprint))
        db.commit()
        if claimed.rowcount != 1:
            continue
        scenario = db.query(ScenarioTemplate).filter_by(scenario_key=progress.scenario_key).first()
        title = scenario.title if scenario else "Удалённый сценарий"
        alerts.append(f"Карточка №{progress.employee_id}, диалог №{progress.id}: {title}")
    if alerts:
        try:
            await notify_hr(messenger, "Нужна проверка сценариев: нет движения больше 3 часов.\n"
                            + "\n".join(alerts[:20])
                            + (f"\nЕщё записей: {len(alerts) - 20}" if len(alerts) > 20 else "")
                            + "\nАвтоматический повтор отключён: доставка может быть неоднозначной. "
                            "Откройте карточку → Сценарии → Очередь сценариев.")
        except Exception:
            logger.warning("Scenario watchdog digest delivery failed: count=%s", len(alerts))
