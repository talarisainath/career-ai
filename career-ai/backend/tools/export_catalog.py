"""Export the frontend JavaScript catalog into canonical JSON for the backend.

The frontend `careers-data.js` remains the human-edited source of career
content. This maintenance tool converts its JavaScript object literals into
strict JSON so the backend and its seed data cannot drift from the site.

Run from the project root:

    python backend/tools/export_catalog.py

The generated file is `backend/app/data/careers.json`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
PROJECT = BACKEND.parent
SOURCE = PROJECT / "careers-data.js"
OUTPUT = BACKEND / "app" / "data" / "careers.json"


def extract_literal(source: str, name: str) -> str:
    """Return the source text of `const <name> = <literal>;`."""
    marker = "const " + name + " = "
    try:
        start = source.index(marker) + len(marker)
    except ValueError as exc:  # pragma: no cover - defensive
        raise SystemExit(f"Could not find declaration for {name!r}") from exc

    opening = source[start]
    closing = {"[": "]", "{": "}"}.get(opening)
    if closing is None:
        # Scalar declaration (not used by this project) -- read one line.
        return source[start:source.index(";", start)]

    depth = 0
    in_string: str | None = None
    escaped = False
    i = start
    while i < len(source):
        ch = source[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
        elif ch in ("'", '"'):
            in_string = ch
        elif ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise SystemExit(f"Unterminated literal for {name!r}")


def js_object_to_json(text: str) -> str:
    """Convert a JSON-compatible JS object/array literal to strict JSON.

    The project's literals already use double-quoted strings; the only
    JavaScript-isms are unquoted keys and (possibly) trailing commas. This
    scanner is string-aware, so content such as URLs or prose is untouched.
    """
    out: list[str] = []
    i = 0
    length = len(text)
    in_string: str | None = None

    while i < length:
        ch = text[i]

        if in_string is not None:
            out.append(ch)
            if ch == "\\" and i + 1 < length:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = ch
            out.append('"')
            i += 1
            continue

        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = length if end == -1 else end + 2
            continue

        if text.startswith("//", i):
            end = text.find("\n", i + 2)
            i = length if end == -1 else end
            continue

        if ch.isalpha() or ch in "_$":
            end = i + 1
            while end < length and (text[end].isalnum() or text[end] in "_-$"):
                end += 1
            word = text[i:end]
            lookahead = end
            while lookahead < length and text[lookahead].isspace():
                lookahead += 1
            if lookahead < length and text[lookahead] == ":":
                out.append('"' + word + '"')
            else:
                out.append(word)
            i = end
            continue

        out.append(ch)
        i += 1

    rendered = "".join(out)
    rendered = re.sub(r",\s*([\]}])", r"\1", rendered)
    return rendered


def parse(source: str, name: str):
    return json.loads(js_object_to_json(extract_literal(source, name)))


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Frontend catalog not found: {SOURCE}")

    source = SOURCE.read_text(encoding="utf-8")

    careers = parse(source, "careers")
    meta = {
        "skillLabels": parse(source, "SKILL_LABELS"),
        "skillOrder": parse(source, "SKILL_ORDER"),
        "interestLabels": parse(source, "INTEREST_LABELS"),
        "interestOrder": parse(source, "INTEREST_ORDER"),
        "workStyleLabels": parse(source, "WORK_STYLE_LABELS"),
        "workStyleOrder": parse(source, "WORK_STYLE_ORDER"),
        "subjectLabels": parse(source, "SUBJECT_LABELS"),
        "subjectOrder": parse(source, "SUBJECT_ORDER"),
        "educationLevels": parse(source, "EDUCATION_LEVELS"),
        "branches": parse(source, "BRANCHES"),
    }

    # --- Integrity checks -------------------------------------------------
    if len(careers) != 17:
        raise SystemExit(f"Expected 17 careers, found {len(careers)}")
    if len({c["id"] for c in careers}) != len(careers):
        raise SystemExit("Duplicate career ids found")

    required = [
        "id", "title", "category", "shortDescription", "overview",
        "responsibilities", "coreSkills", "interests", "educationPathways",
        "subjects", "subjectWeights", "beginnerProjects", "skillsToLearn",
        "resources", "workStyles", "educationNote",
    ]
    known_skills = set(meta["skillLabels"])
    known_interests = set(meta["interestLabels"])
    known_styles = set(meta["workStyleLabels"])
    known_subjects = set(meta["subjectLabels"])

    for career in careers:
        missing = [field for field in required if field not in career]
        if missing:
            raise SystemExit(f"{career.get('id')}: missing fields {missing}")
        unknown_skills = set(career["coreSkills"]) - known_skills
        unknown_interests = set(career["interests"]) - known_interests
        unknown_styles = set(career["workStyles"]) - known_styles
        unknown_weights = set(career["subjectWeights"]) - known_subjects
        if unknown_skills or unknown_interests or unknown_styles or unknown_weights:
            raise SystemExit(
                f"{career['id']}: unknown keys "
                f"{unknown_skills | unknown_interests | unknown_styles | unknown_weights}"
            )
        # Subject weights are relative and are normalised by the engine over
        # the subjects the student actually recorded, so they need not sum to 1.
        if not career["subjectWeights"] or sum(career["subjectWeights"].values()) <= 0:
            raise SystemExit(f"{career['id']}: subject weights must be positive")

    payload = {"meta": meta, "careers": careers}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(careers)} careers to {OUTPUT}")
    print("Categories:", ", ".join(sorted({c['category'] for c in careers})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
