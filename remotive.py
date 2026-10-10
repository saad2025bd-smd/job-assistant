import requests
from datetime import datetime
from typing import List, Optional
from .base import Job


def fetch_jobs(search: Optional[str] = None, max_jobs: int = 50) -> List[Job]:
    """Fetch jobs from Remotive public API (no key required)."""
    url = "https://remotive.com/api/remote-jobs"
    params = {}
    if search:
        params["search"] = search
    if max_jobs:
        params["limit"] = max_jobs

    headers = {
        "User-Agent": "JobAssistant/1.0 (personal job search tool)"
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Remotive] Error: {e}")
        return []

    jobs: List[Job] = []
    for item in data.get("jobs", []):
        if len(jobs) >= max_jobs:
            break

        external_id = str(item.get("id") or item.get("url", ""))
        title = item.get("title") or "Unknown"
        company = item.get("company_name") or "Unknown"
        description = item.get("description") or ""
        tags = item.get("tags") or []
        category = item.get("category")
        if category:
            tags = list(set(tags + [category.lower()]))
        location = item.get("candidate_required_location") or "Worldwide"
        job_url = item.get("url") or item.get("job_url") or ""

        salary_text = item.get("salary") or ""
        published = None
        if item.get("publication_date"):
            try:
                published = datetime.fromisoformat(
                    item["publication_date"].replace("Z", "+00:00")
                )
            except Exception:
                pass

        jobs.append(Job(
            id=Job.make_id("remotive", external_id),
            title=title.strip(),
            company=company.strip(),
            url=job_url,
            source="remotive",
            description=description,
            location=location,
            tags=[t.lower() for t in tags if t],
            salary_text=salary_text,
            published_at=published,
            raw=item,
        ))
    return jobs