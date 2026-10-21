import json
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import ProductionCalendarVersion, ProductionCalendarYear
from ..production_calendar import MAX_UPLOAD, parse_calendar
from ..time_utils import utc_now
from .support import require_api_admin

router = APIRouter()


def get_db():
    with get_session() as db:
        yield db


def _summary(version: ProductionCalendarVersion) -> dict:
    days = json.loads(version.days_json)
    return {"id": version.id, "year": version.year, "source_name": version.source_name,
            "created_at": version.created_at.isoformat(), "digest": version.digest,
            "workdays": sum(day["is_workday"] for day in days), "days_off": sum(not day["is_workday"] for day in days),
            "shortened": sum(day["is_shortened"] for day in days)}


@router.get("/api/settings/production-calendars")
def calendars(request: Request, db: Session = Depends(get_db)):
    require_api_admin(request)
    active = {row.year: row.current_version_id for row in db.query(ProductionCalendarYear)}
    return {"versions": [{**_summary(row), "is_current": active.get(row.year) == row.id}
                         for row in db.query(ProductionCalendarVersion).order_by(ProductionCalendarVersion.year.desc(), ProductionCalendarVersion.id.desc())]}


@router.post("/api/settings/production-calendars/import")
async def import_calendar(request: Request, file: UploadFile = File(...), mode: str = Form("preview"),
                          expected_digest: str = Form(""), expected_version_id: int = Form(0), db: Session = Depends(get_db)):
    actor = require_api_admin(request)
    if mode not in {"preview", "apply"}:
        raise HTTPException(status_code=422, detail="Неизвестный режим импорта")
    content = await file.read(MAX_UPLOAD + 1)
    try:
        parsed = parse_calendar(content, file.filename or "")
    except (ValueError, TypeError, KeyError, UnicodeError, zipfile.BadZipFile, OSError) as exc:
        raise HTTPException(status_code=422, detail="Календарь не принят: " + str(exc)[:220]) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Не удалось прочитать файл календаря") from exc
    year = parsed["year"]
    current = db.get(ProductionCalendarYear, year)
    current_id = current.current_version_id if current else None
    previous = db.get(ProductionCalendarVersion, current_id) if current_id else None
    previous_days = {row["date"]: row for row in json.loads(previous.days_json)} if previous else {}
    changes = sum(previous_days.get(row["date"]) != row for row in parsed["days"])
    if mode == "preview":
        return {**parsed, "expected_version_id": current_id or 0, "changed_days": changes}
    if expected_digest != parsed["digest"] or expected_version_id != (current_id or 0):
        raise HTTPException(status_code=409, detail="Файл или календарь изменился. Повторите предпросмотр.")
    if previous and previous.digest == parsed["digest"]:
        return {"message": "Этот календарь уже сохранён", "version": _summary(previous)}
    # The annual pointer is the compare-and-swap lock; versions are immutable.
    db.execute(insert(ProductionCalendarYear).values(year=year).on_conflict_do_nothing(index_elements=["year"]))
    version = ProductionCalendarVersion(year=year, digest=parsed["digest"], days_json=json.dumps(parsed["days"], ensure_ascii=False),
                                        source_name=(file.filename or "calendar").replace("\\", "/").split("/")[-1][:255],
                                        created_at=utc_now(), created_by=actor.id)
    db.add(version)
    db.flush()
    claim = db.execute(update(ProductionCalendarYear).where(ProductionCalendarYear.year == year,
                       ProductionCalendarYear.current_version_id == (expected_version_id or None))
                       .values(current_version_id=version.id).execution_options(synchronize_session=False))
    if claim.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Другой администратор обновил календарь. Повторите предпросмотр.")
    db.commit()
    return {"message": "Календарь сохранён. Расписания не изменены.", "version": _summary(version)}
