from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import re

from .config import settings


_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_filename(name: str) -> str:
    base = (name or "file.bin").strip()
    cleaned = _SAFE_NAME_RE.sub("_", base)
    return cleaned[:180] or "file.bin"


def ensure_storage_dir() -> Path:
    storage = Path(settings.FILE_STORAGE_DIR).expanduser().resolve()
    storage.mkdir(parents=True, exist_ok=True)
    return storage


def build_employee_file_path(employee_id: int, original_filename: str) -> Path:
    root = ensure_storage_dir()
    employee_dir = root / str(employee_id)
    employee_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(original_filename)
    return employee_dir / f"{uuid4().hex}_{safe_name}"


def build_step_attachment_path(scenario_key: str, step_key: str, original_filename: str) -> Path:
    root = ensure_storage_dir().parent / "scenario_step_files"
    step_dir = root / scenario_key
    step_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(original_filename)
    safe_step_key = _safe_filename(step_key)
    return step_dir / f"{safe_step_key}_{uuid4().hex}_{safe_name}"
