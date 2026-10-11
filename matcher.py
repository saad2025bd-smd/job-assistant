"""Simple keyword + preference based job matching."""
from typing import List, Dict, Any, Tuple
from base import Job
import re


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9+#\.]+", text.lower()))


def score_job(job: Job, profile: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """
    Return (score 0-1, breakdown).
    Higher is better match.
    """
    breakdown = {
        "role_match": 0.0,
        "skill_match": 0.0,
        "location_match": 0.0,
        "exclude_penalty": 0.0,
        "salary_bonus": 0.0,
    }

    text = f"{job.title} {job.description} {' '.join(job.tags)}".lower()
    tokens = _tokenize(text)

    # --- Role match ---
    target_roles = [r.lower() for r in profile.get("target_roles", [])]
    role_hits = 0
    for role in target_roles:
        role_tokens = _tokenize(role)
        if role_tokens and role_tokens.issubset(tokens) or any(t in text for t in role_tokens):
            role_hits += 1
    if target_roles:
        breakdown["role_match"] = min(1.0, role_hits / max(1, len(target_roles) * 0.6))

    # --- Skills match ---
    skills_section = profile.get("skills", {})
    all_skills = []
    for key in ("languages", "frameworks", "tools", "soft_skills"):
        all_skills.extend([s.lower() for s in skills_section.get(key, [])])
    # Skills extracted from uploaded CV
    docs = profile.get("documents", {}) or {}
    for s in (docs.get("cv_skills") or []):
        all_skills.append(str(s).lower())

    skill_hits = sum(1 for s in all_skills if s in text or s in tokens)
    if all_skills:
        breakdown["skill_match"] = min(1.0, skill_hits / max(3, len(all_skills) * 0.4))

    # --- Location / remote preference ---
    prefs = profile.get("preferences", {})
    want_remote = prefs.get("remote", True)
    preferred_locs = [l.lower() for l in prefs.get("locations", [])]
    job_loc = (job.location or "").lower()

    if want_remote and ("remote" in job_loc or "worldwide" in job_loc or "anywhere" in job_loc):
        breakdown["location_match"] = 1.0
    elif any(loc in job_loc for loc in preferred_locs):
        breakdown["location_match"] = 0.85
    elif want_remote is False and "remote" not in job_loc:
        breakdown["location_match"] = 0.7
    else:
        breakdown["location_match"] = 0.3

    # --- Exclude keywords ---
    excludes = [e.lower() for e in prefs.get("exclude_keywords", [])]
    for excl in excludes:
        if excl in text:
            breakdown["exclude_penalty"] = -0.8
            break

    # --- Salary bonus (soft) ---
    salary_min_pref = prefs.get("salary_min")
    if salary_min_pref and job.salary_min:
        if job.salary_min >= salary_min_pref:
            breakdown["salary_bonus"] = 0.15
        elif job.salary_max and job.salary_max >= salary_min_pref:
            breakdown["salary_bonus"] = 0.08

    # Weighted total
    score = (
        0.35 * breakdown["role_match"]
        + 0.40 * breakdown["skill_match"]
        + 0.20 * breakdown["location_match"]
        + breakdown["exclude_penalty"]
        + breakdown["salary_bonus"]
    )
    score = max(0.0, min(1.0, score))
    return score, breakdown


def rank_jobs(jobs: List[Job], profile: Dict[str, Any], min_score: float = 0.35) -> List[Tuple[Job, float, Dict]]:
    """Return list of (job, score, breakdown) sorted by score desc, filtered by min_score."""
    scored = []
    for job in jobs:
        score, breakdown = score_job(job, profile)
        if score >= min_score:
            scored.append((job, score, breakdown))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored