"""Python port of `recommendation-engine.js`.

The formulas, weights, coverage scaling, ordering, explanations and skill-gap
logic are ported line-for-line from the verified JavaScript engine. Keep this
file and the JS engine in sync: `tests/test_parity.py` compares real outputs
captured from the browser engine against this implementation.

This is a transparent, rule-based match score. It is not a trained model and
is not a probability of career success.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from ..catalog import branch_labels, label_maps

WEIGHTS: dict[str, float] = {
    "skills": 0.40,
    "interests": 0.25,
    "academics": 0.20,
    "preferences": 0.15,
}

TOP_N = 5

INSUFFICIENT_MESSAGE = (
    "There is not enough information to rank careers yet. "
    "Please complete at least two sections of the assessment "
    "(skills, interests, academics, or work preferences)."
)

# Informational only: which categories relate to which academic branch.
# Never affects the score.
BRANCH_RELEVANCE: dict[str, list[str]] = {
    "computer-science": ["Software & Technology", "Data & AI"],
    "electronics": ["Engineering"],
    "electrical": ["Engineering"],
    "mechanical": ["Engineering"],
    "civil": ["Engineering"],
    "science": ["Science & Research", "Data & AI"],
    "commerce": ["Business & Finance"],
    "arts": ["Media & Communication", "Education"],
    "other": [],
}


# ---------------------------------------------------------------------------
# Helpers (mirroring the JS helpers)
# ---------------------------------------------------------------------------


def clamp01(value: Any) -> float:
    """JS clamp01: non-numbers and non-finite values become 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    numeric = float(value)
    if not math.isfinite(numeric):
        return 0.0
    return min(1.0, max(0.0, numeric))


def js_round(value: float) -> int:
    """JS Math.round rounds half up (towards +Infinity), not banker's."""
    return int(math.floor(value + 0.5))


def _js_number(value: Any) -> str:
    """Format a number the way JavaScript's String(number) does for marks."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value)


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _intersection(first: Iterable[str], second: Iterable[str]) -> list[str]:
    target = set(second)
    return [item for item in first if item in target]


def _labels_for(keys: Iterable[str], label_map: dict[str, str]) -> list[str]:
    return [label_map.get(key, key) for key in keys]


# ---------------------------------------------------------------------------
# Component scores (0..1, or None when unavailable)
# ---------------------------------------------------------------------------


def score_skills(profile: dict[str, Any], career: dict[str, Any]) -> float | None:
    selected = profile.get("skills") or {}
    if len(selected) == 0 or not career.get("coreSkills"):
        return None

    total = 0.0
    for skill in career["coreSkills"]:
        if skill in selected:
            total += clamp01(selected[skill] / 5)
    return total / len(career["coreSkills"])


def score_interests(profile: dict[str, Any], career: dict[str, Any]) -> float | None:
    user = profile.get("interests") or []
    target = career.get("interests") or []
    if len(user) == 0 or len(target) == 0:
        return None
    shared = len(_intersection(user, target))
    return clamp01(shared / min(len(user), len(target)))


def score_academics(profile: dict[str, Any], career: dict[str, Any]) -> float | None:
    marks = profile.get("subjects") or {}
    weights = career.get("subjectWeights") or {}

    weighted = 0.0
    total_weight = 0.0
    for subject, weight in weights.items():
        mark = marks.get(subject)
        if _is_number(mark):
            weighted += weight * float(mark)
            total_weight += weight

    if total_weight == 0:
        return None
    return clamp01((weighted / total_weight) / 100)


def score_preferences(profile: dict[str, Any], career: dict[str, Any]) -> float | None:
    user = profile.get("workStyles") or []
    target = career.get("workStyles") or []
    if len(user) == 0 or len(target) == 0:
        return None
    shared = len(_intersection(user, target))
    return clamp01(shared / min(len(user), len(target)))


# ---------------------------------------------------------------------------
# Explainability
# ---------------------------------------------------------------------------


def build_reasons(
    profile: dict[str, Any],
    career: dict[str, Any],
    components: dict[str, float | None],
) -> list[str]:
    labels = label_maps()
    skill_labels = labels["skills"]
    interest_labels = labels["interests"]
    style_labels = labels["workStyles"]
    subject_labels = labels["subjects"]

    reasons: list[str] = []
    held = profile.get("skills") or {}
    core_skills = career.get("coreSkills") or []

    matched_skills = [skill for skill in core_skills if skill in held]
    if matched_skills and components["skills"] is not None:
        strong = [skill for skill in matched_skills if held[skill] >= 4]
        text = (
            f"Matches {len(matched_skills)} of {len(core_skills)} core skills "
            f"({', '.join(_labels_for(matched_skills, skill_labels))})"
        )
        if len(strong) >= 2:
            text += ", several of which you rated as advanced"
        reasons.append(text + ".")

    shared_interests = _intersection(profile.get("interests") or [], career.get("interests") or [])
    if shared_interests and components["interests"] is not None:
        reasons.append(
            "You selected the interests "
            + " and ".join(_labels_for(shared_interests, interest_labels))
            + ", which sit at the centre of this work."
        )

    if components["academics"] is not None:
        marks = profile.get("subjects") or {}
        relevant = [subject for subject in (career.get("subjectWeights") or {}) if subject in marks]
        if relevant:
            parts = [
                f"{subject_labels.get(subject, subject)} ({_js_number(marks[subject])}%)"
                for subject in relevant
            ]
            reasons.append(
                "Your marks in "
                + ", ".join(parts)
                + " are relevant to this career's typical subject focus."
            )

    shared_styles = _intersection(profile.get("workStyles") or [], career.get("workStyles") or [])
    if shared_styles and components["preferences"] is not None:
        reasons.append(
            "Your preferred work style — "
            + ", ".join(_labels_for(shared_styles, style_labels))
            + " — is central to how this role is carried out."
        )

    branch = profile.get("branch")
    if branch and career.get("category") in BRANCH_RELEVANCE.get(branch, []):
        branch_label = branch_labels().get(branch, branch)
        reasons.append(
            f"Your academic background ({branch_label}) relates directly to this field."
        )

    if not reasons:
        reasons.append(
            "This career shares some ground with the information you provided, "
            "but the profile was too limited for a strong signal."
        )
    return reasons


def build_skill_gaps(profile: dict[str, Any], career: dict[str, Any]) -> list[str]:
    held = profile.get("skills") or {}
    return [skill for skill in career.get("coreSkills", []) if skill not in held]


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------


def profile_availability(profile: dict[str, Any]) -> dict[str, bool]:
    subjects = profile.get("subjects") or {}
    return {
        "skills": len(profile.get("skills") or {}) > 0,
        "interests": len(profile.get("interests") or []) > 0,
        "academics": any(_is_number(value) for value in subjects.values()),
        "preferences": len(profile.get("workStyles") or []) > 0,
    }


def final_score(raw: dict[str, float | None], availability: dict[str, bool]) -> float:
    """Weighted, coverage-scaled score in 0..1 (before 0-100 rounding).

    Exposed separately so the verified 15/67/76/100 -> 53 example can be
    tested directly as well as end-to-end.
    """
    available_keys = [key for key in WEIGHTS if availability.get(key)]
    weight_total = sum(WEIGHTS[key] for key in available_keys)
    if weight_total == 0:
        return 0.0

    score = 0.0
    used_weight = 0.0
    for key in WEIGHTS:
        if raw.get(key) is None or not availability.get(key):
            continue
        normalized = WEIGHTS[key] / weight_total
        score += normalized * raw[key]
        used_weight += normalized

    score = score / used_weight if used_weight > 0 else 0.0
    coverage = weight_total
    return clamp01(score * (0.5 + 0.5 * coverage))


def recommend(profile: dict[str, Any], career_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank careers for a validated assessment profile.

    `career_records` uses the API's camelCase dictionaries (Career.to_dict()).
    """
    availability = profile_availability(profile)
    available_keys = [key for key in WEIGHTS if availability[key]]

    if len(available_keys) < 2:
        return {
            "status": "insufficient",
            "source": "python-rule-based",
            "message": INSUFFICIENT_MESSAGE,
            "matches": [],
        }

    weight_total = sum(WEIGHTS[key] for key in available_keys)
    coverage = weight_total

    matches: list[dict[str, Any]] = []
    for career in career_records:
        raw: dict[str, float | None] = {
            "skills": score_skills(profile, career),
            "interests": score_interests(profile, career),
            "academics": score_academics(profile, career),
            "preferences": score_preferences(profile, career),
        }

        # Redistribute weight across components that exist for this career.
        score = 0.0
        used_weight = 0.0
        used_weights: dict[str, float] = {}
        for key in WEIGHTS:
            if raw[key] is None or not availability[key]:
                continue
            normalized = WEIGHTS[key] / weight_total
            score += normalized * raw[key]
            used_weight += normalized
            used_weights[key] = normalized
        score = score / used_weight if used_weight > 0 else 0.0
        score *= 0.5 + 0.5 * coverage

        components = {
            "skills": None if raw["skills"] is None else js_round(raw["skills"] * 100),
            "interests": None if raw["interests"] is None else js_round(raw["interests"] * 100),
            "academics": None if raw["academics"] is None else js_round(raw["academics"] * 100),
            "preferences": None if raw["preferences"] is None else js_round(raw["preferences"] * 100),
        }

        held = profile.get("skills") or {}
        matched_skills = [skill for skill in career.get("coreSkills", []) if skill in held]
        matched_interests = _intersection(
            profile.get("interests") or [], career.get("interests") or []
        )

        matches.append(
            {
                "id": career["id"],
                "title": career["title"],
                "category": career["category"],
                "shortDescription": career["shortDescription"],
                "score": js_round(clamp01(score) * 100),
                "components": components,
                "weightsUsed": used_weights,
                "matchedSkills": matched_skills,
                "matchedInterests": matched_interests,
                "reasons": build_reasons(profile, career, raw),
                "skillGaps": build_skill_gaps(profile, career),
            }
        )

    # Same ordering as the JS engine: score desc, then skills component desc,
    # then title (localeCompare).
    matches.sort(
        key=lambda match: (
            -match["score"],
            -(match["components"]["skills"] if match["components"]["skills"] is not None else -1),
            match["title"].casefold(),
            match["title"],
        )
    )
    for index, match in enumerate(matches, start=1):
        match["rank"] = index

    return {
        "status": "ok",
        "source": "python-rule-based",
        "matches": matches,
        "topN": TOP_N,
        "coverage": js_round(coverage * 100),
    }
