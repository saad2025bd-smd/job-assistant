"""Generate tailored application materials (cover letter, notes)."""
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Template
from base import Job
import re


COVER_LETTER_TEMPLATE = """
Dear Hiring Team at {{ company }},

I am writing to express my interest in the {{ title }} position{% if location %} ({{ location }}){% endif %}.

{{ intro }}

{{ body }}

{{ closing }}

Best regards,
{{ full_name }}
{% if email %}{{ email }}{% endif %}
{% if phone %}{{ phone }}{% endif %}
{% if linkedin %}{{ linkedin }}{% endif %}
""".strip()


def _extract_key_requirements(description: str, max_items: int = 6) -> list:
    """Very lightweight keyword extraction from job description."""
    # Look for common requirement patterns
    lines = re.split(r"[\n•\-\*]", description)
    candidates = []
    keywords = ["experience", "knowledge", "proficient", "familiar", "strong", "must", "required", "prefer"]
    for line in lines:
        line = line.strip()
        if 20 < len(line) < 180 and any(k in line.lower() for k in keywords):
            candidates.append(line)
        if len(candidates) >= max_items:
            break
    return candidates[:max_items]


def generate_cover_letter(job: Job, profile: Dict[str, Any]) -> str:
    """Generate a tailored cover letter using simple rules + template."""
    personal = profile.get("personal", {})
    skills = profile.get("skills", {})
    prefs = profile.get("cover_letter", {})
    # Prefer full CV text when available, else short summary
    documents = profile.get("documents", {}) or {}
    cv_text = (documents.get("cv_text") or "").strip()
    experience = (profile.get("experience_summary") or "").strip()
    if cv_text and len(cv_text) > len(experience):
        # Use a condensed slice of the CV for the letter body
        experience = cv_text[:900].rsplit(" ", 1)[0] + ("…" if len(cv_text) > 900 else "")

    # Build skill highlights relevant to the job
    all_skills = []
    for key in ("languages", "frameworks", "tools"):
        all_skills.extend(skills.get(key, []))
    # Merge skills detected from CV
    for s in (documents.get("cv_skills") or []):
        if s not in all_skills:
            all_skills.append(s)

    job_text = f"{job.title} {job.description} {' '.join(job.tags)}".lower()
    relevant_skills = [s for s in all_skills if s.lower() in job_text]
    if not relevant_skills:
        relevant_skills = all_skills[:5]

    skill_phrase = ", ".join(relevant_skills[:6])

    intro = (
        f"With my background in {skill_phrase}, I believe I would be a strong fit for this role. "
        f"I am particularly excited about the opportunity to contribute at {job.company}."
    )

    body_parts = []
    if experience:
        body_parts.append(experience)

    if relevant_skills:
        body_parts.append(
            f"My experience with {', '.join(relevant_skills[:4])} aligns well with the requirements of this position."
        )

    # Mention 1-2 key requirements if we can extract them
    reqs = _extract_key_requirements(job.description)
    if reqs:
        body_parts.append(
            "I have reviewed the requirements and am confident I can deliver on the key areas highlighted in the posting."
        )

    body = "\n\n".join(body_parts)

    closing = (
        "I would welcome the chance to discuss how my skills and experience can support your team. "
        "Thank you for your time and consideration."
    )

    template = Template(COVER_LETTER_TEMPLATE)
    letter = template.render(
        company=job.company,
        title=job.title,
        location=job.location,
        intro=intro,
        body=body,
        closing=closing,
        full_name=personal.get("full_name", "Candidate"),
        email=personal.get("email", ""),
        phone=personal.get("phone", ""),
        linkedin=personal.get("linkedin", ""),
    )
    return letter.strip() + "\n"


def generate_application_notes(job: Job, profile: Dict[str, Any], score: float, breakdown: Dict) -> str:
    """Short internal notes for the user before applying."""
    notes = [
        f"# Application Prep — {job.title} @ {job.company}",
        f"**Source:** {job.source}  |  **Match score:** {score:.0%}",
        f"**URL:** {job.url}",
        f"**Location:** {job.location}",
        "",
        "## Why this looks relevant",
    ]
    if breakdown.get("role_match", 0) > 0.5:
        notes.append("- Strong title / role match")
    if breakdown.get("skill_match", 0) > 0.4:
        notes.append("- Good overlap with your listed skills")
    if breakdown.get("location_match", 0) > 0.7:
        notes.append("- Location / remote preference matches")
    if breakdown.get("salary_bonus", 0) > 0:
        notes.append("- Salary appears within or above your target")

    notes.extend([
        "",
        "## Suggested talking points",
        "- Highlight projects that used the overlapping skills above",
        "- Mention measurable impact (latency, revenue, users, reliability)",
        "- Be ready to discuss why you want this company specifically",
        "",
        "## Next steps (semi-automated)",
        "1. Review the generated cover letter",
        "2. Open the job URL and apply manually (or use browser fill helpers)",
        "3. Mark the job as 'applied' in the tracker after submitting",
        "",
    ])
    return "\n".join(notes)


def save_materials(job: Job, cover_letter: str, notes: str, output_dir: Path) -> Path:
    """Save cover letter + notes to a job-specific folder."""
    safe_company = re.sub(r"[^\w\-]+", "_", job.company)[:40]
    safe_title = re.sub(r"[^\w\-]+", "_", job.title)[:50]
    folder_name = f"{datetime.now().strftime('%Y%m%d')}_{safe_company}_{safe_title}"
    folder = output_dir / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "cover_letter.txt").write_text(cover_letter, encoding="utf-8")
    (folder / "notes.md").write_text(notes, encoding="utf-8")
    (folder / "job_meta.txt").write_text(
        f"Title: {job.title}\nCompany: {job.company}\nURL: {job.url}\nSource: {job.source}\nLocation: {job.location}\n",
        encoding="utf-8",
    )
    return folder