"""Read Skills-style templates separately from survey sheets and staff results."""
from io import BytesIO
import hashlib
import zipfile

from openpyxl import load_workbook

LEVELS = {"нет": 0, "понимание": 1, "умение": 2, "экспертность": 3, "экспертиза": 3, "лидерство": 4}
IMPORTANCE = {"обычный": 1, "ключевой": 2, "критичный": 3}


def parse_skills_workbook(content, sheet_name="Системный аналитик", blank_requirements_zero=False):
    if len(content) > 5_000_000:
        raise ValueError("Workbook exceeds 5 MB")
    with zipfile.ZipFile(BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 50_000_000:
            raise ValueError("Expanded workbook exceeds 50 MB")
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
    try:
        if sheet_name not in workbook.sheetnames:
            raise ValueError("Worksheet not found")
        sheet = workbook[sheet_name]
        rows = list(sheet.iter_rows(min_row=1, max_row=1000, max_col=100, values_only=True))
        headers = rows[0]
        if list(headers[:7]) != ["Категория", "Навык", "Junior", "Middle", "Senior", "Lead", "Важность"]:
            raise ValueError("Worksheet is not a competency matrix")
        categories = {}
        candidates = [{"column": index + 1, "name": value.strip(), "grade": rows[1][index], "values": []}
                      for index, value in enumerate(headers) if index >= 7 and isinstance(value, str) and value.strip() and not value.strip().lower().startswith("столбец")]
        warnings = []
        seen = set()
        for row_number, values in enumerate(rows[2:], 3):
            category, skill = values[:2]
            if category is None and skill is None:
                continue
            if not isinstance(category, str) or not isinstance(skill, str):
                raise ValueError(f"Invalid category/skill at row {row_number}")
            if any(isinstance(value, str) and value.startswith("=") for value in values[:7]):
                raise ValueError(f"Formulas must be replaced with reviewed values at row {row_number}")
            key = (category.strip(), skill.strip())
            if key in seen:
                raise ValueError(f"Duplicate competency at row {row_number}")
            seen.add(key)
            levels = {}
            for slug, value in zip(("junior", "middle", "senior", "lead"), values[2:6]):
                if value is None and blank_requirements_zero:
                    value = "Нет"
                    warnings.append(f"{row_number}/{slug}: пустое требование принято как 0")
                if not isinstance(value, str) or value.strip().lower() not in LEVELS:
                    raise ValueError(f"Unknown requirement at row {row_number}/{slug}")
                levels[slug] = LEVELS[value.strip().lower()]
            importance = IMPORTANCE.get(str(values[6]).strip().lower())
            if importance is None:
                raise ValueError(f"Unknown importance at row {row_number}")
            categories.setdefault(key[0], []).append({"name": key[1], "importance": importance, "levels": levels})
            for candidate in candidates:
                raw = values[candidate["column"] - 1]
                if isinstance(raw, str) and raw.startswith("="):
                    raise ValueError(f"Formula score requires reviewed values at row {row_number}")
                if raw is None or str(raw).strip().lower() in {"н/д", "n/a", "нет данных"}:
                    level = None
                elif type(raw) in (int, float) and raw == int(raw) and 0 <= raw <= 4:
                    level = int(raw)
                else:
                    raise ValueError(f"Invalid employee score at row {row_number}, column {candidate['column']}")
                candidate["values"].append({"category": key[0], "skill": key[1], "level": level, "row": row_number})
        if not seen:
            raise ValueError("No competencies found")
        return {"catalog": {"specialization": {"name": sheet_name}, "categories": [{"name": key, "skills": skills} for key, skills in categories.items()]},
                "assessment_candidates": candidates, "warnings": warnings,
                "source_digest": hashlib.sha256(content).hexdigest(), "sheet": sheet_name}
    finally:
        workbook.close()
