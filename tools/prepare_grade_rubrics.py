"""Prepare reviewable catalog JSON from approved rubrics and the original Skills matrix.

This converter never connects to a database or imports employee assessments.
"""
import argparse
import hashlib
import json
from pathlib import Path

import openpyxl

PAIRS = {
    "РП (Project Managers)": "РП",
    "Дизайнер Сервисов": "Дизайнер сервисов",
    "Дизайнер Концептов": "Дизайнер концептов",
    "Бизнес-аналитик (BA)": "Бизнес аналитик",
    "Системный аналитик (SA)": "Системный аналитик",
}
NAMES = {"РП": "Руководитель проектов"}
WEIGHTS = {"Обычный": 1, "Ключевой": 2, "Критичный": 3}
LEVELS = {"нет": 0, "понимание": 1, "умение": 2, "экспертность": 3, "экспертиза": 3, "лидерство": 4}


def normalize(text):
    return " ".join(str(text).strip().lower().replace("ё", "е").split())


def prepare(questions_path, skills_path):
    questions = openpyxl.load_workbook(questions_path, read_only=True, data_only=True)
    original = openpyxl.load_workbook(skills_path, read_only=True, data_only=True)
    try:
        intro = questions["Начало"]["B3"].value
        open_questions = [questions["Начало"][f"B{r}"].value for r in (7, 9, 10)]
        packages = []
        for source, target in PAIRS.items():
            old = {}
            category = None
            for row in original[target].iter_rows(min_row=2, max_col=6, values_only=True):
                if row[0]:
                    category = row[0]
                if row[1]:
                    old[normalize(row[1])] = (category, row)
            sheet = questions[source]
            headers = [cell.value for cell in sheet[3]]
            index = {value: i for i, value in enumerate(headers) if value}
            answer_columns = [i for i, value in enumerate(headers) if isinstance(value, str) and value.startswith("Вариант ") and value != "Вариант N/A"]
            if len(answer_columns) != 4:
                raise ValueError(f"Expected four anchors: {source}")
            categories, seen = {}, set()
            added = []
            for row in sheet.iter_rows(min_row=4, values_only=True):
                if not row[0]:
                    continue
                name = row[index["Компетенция"]].strip()
                key = normalize(name)
                if key in seen:
                    raise ValueError(f"Duplicate competency: {source}/{name}")
                seen.add(key)
                previous = old.get(key)
                if previous:
                    cat, previous_row = previous
                    levels = {slug: int(value) if isinstance(value, (int, float)) else LEVELS[normalize(value)] if value else 0
                              for slug, value in zip(("junior", "middle", "senior", "lead"), previous_row[2:6])}
                else:
                    if "Категория" not in index:
                        raise ValueError(f"No category for new skill: {name}")
                    cat = row[index["Категория"]]
                    levels = dict(zip(("junior", "middle", "senior", "lead"), (1, 2, 3, 4)))
                    added.append(name)
                rubric = {"levels": {str(i + 1): row[col].strip() for i, col in enumerate(answer_columns)},
                          "na": row[index["Вариант N/A"]].strip()}
                categories.setdefault(cat, []).append({"name": name, "importance": WEIGHTS[row[index["Важность"]]],
                    "levels": levels, "rubric": rubric})
            packages.append({"source_sheet": source, "added": added,
                "removed": [entry[1][1] for key, entry in old.items() if key not in seen],
                "catalog": {"specialization": {"name": NAMES.get(target, target),
                    "assessment_intro": intro, "open_questions": open_questions},
                    "categories": [{"name": key, "skills": value} for key, value in categories.items()]}})
        return {"source_sha256": hashlib.sha256(Path(questions_path).read_bytes()).hexdigest(), "packages": packages}
    finally:
        questions.close()
        original.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", required=True)
    parser.add_argument("--skills", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = prepare(args.questions, args.skills)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({p["source_sheet"]: {"count": sum(len(c["skills"]) for c in p["catalog"]["categories"]),
        "added": p["added"], "removed": p["removed"]} for p in result["packages"]}, ensure_ascii=False))
