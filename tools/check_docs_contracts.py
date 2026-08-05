from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REQUIRED_FRONTMATTER_FIELDS = ("doc_type", "status", "area", "source_of_truth")
ROUTE_DECORATOR_RE = re.compile(r'@(?:router|app)\.(?:get|post|put|patch|delete)\("([^"]+)"')
CONFIG_VAR_RE = re.compile(r"^\s+([A-Z0-9_]+):", re.MULTILINE)
TABLE_RE = re.compile(r'__tablename__\s*=\s*"([^"]+)"')
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"(?s)^---\s*(.*?)\s*---", text)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def wiki_target_exists(target: str) -> bool:
    normalized = target.split("|", 1)[0].split("#", 1)[0].strip()
    if not normalized:
        return True
    return (DOCS / f"{normalized}.md").exists() or (DOCS / normalized).exists()


def check_frontmatter(errors: list[str]) -> None:
    for path in sorted(DOCS.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        text = read(path)
        if not text.strip():
            errors.append(f"{rel}: empty markdown file")
            continue
        fm = frontmatter(text)
        missing = [field for field in REQUIRED_FRONTMATTER_FIELDS if not fm.get(field)]
        if missing:
            errors.append(f"{rel}: missing frontmatter fields: {', '.join(missing)}")
        if rel.startswith("docs/decisions/") and fm.get("doc_type") == "decision":
            errors.append(f"{rel}: use doc_type: adr, not decision")
        if rel.startswith("docs/handoffs/") and fm.get("source_of_truth") == "true":
            errors.append(f"{rel}: handoff must not be source_of_truth: true")


def check_wiki_links(errors: list[str]) -> None:
    for path in sorted(DOCS.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        for match in WIKI_LINK_RE.finditer(read(path)):
            target = match.group(1)
            if not wiki_target_exists(target):
                errors.append(f"{rel}: missing wiki-link target [[{target}]]")


def check_route_docs(errors: list[str]) -> None:
    route_docs = read(DOCS / "api.md") + "\n" + read(DOCS / "web-surface.md")
    route_sources = [ROOT / "app" / "main.py", *sorted((ROOT / "app" / "web").glob("*.py"))]
    for source in route_sources:
        for route in ROUTE_DECORATOR_RE.findall(read(source)):
            if (
                route.startswith("/api/")
                or route.startswith("/app/")
                or route.startswith("/documents")
                or route.startswith("/design-system")
            ) and route not in route_docs:
                errors.append(f"docs/api.md or docs/web-surface.md: missing route {route}")


def check_config_docs(errors: list[str]) -> None:
    config_vars = sorted(set(CONFIG_VAR_RE.findall(read(ROOT / "app" / "config.py"))))
    config_doc = read(DOCS / "configuration.md")
    env_example = read(ROOT / ".env.example")
    for name in config_vars:
        if f"`{name}`" not in config_doc:
            errors.append(f"docs/configuration.md: missing config var `{name}`")
        if f"{name}=" not in env_example:
            errors.append(f".env.example: missing config var {name}")


def check_data_model_docs(errors: list[str]) -> None:
    tables = sorted(set(TABLE_RE.findall(read(ROOT / "app" / "models.py"))))
    data_doc = read(DOCS / "data-model.md")
    for table in tables:
        if f"`{table}`" not in data_doc:
            errors.append(f"docs/data-model.md: missing table `{table}`")


def main() -> int:
    errors: list[str] = []
    check_frontmatter(errors)
    check_wiki_links(errors)
    check_route_docs(errors)
    check_config_docs(errors)
    check_data_model_docs(errors)
    if errors:
        print("Docs contract check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Docs contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
