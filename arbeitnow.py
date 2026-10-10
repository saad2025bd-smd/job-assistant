import requests
from datetime import datetime
from typing import List
from base import Job


def fetch_jobs(max_jobs: int = 50) -> List[Job]:
    """Fetch jobs from Arbeitnow public API (no key required). Strong on EU/remote."""
    url = "https://www.arbeitnow.com/api/job-board-api"
    headers = {
        "User-Agent": "JobAssistant/1.0 (personal job search tool)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Arbeitnow] Error: {e}")
        return []

    jobs: List[Job] = []
    for item in data.get("data", []):
        if len(jobs) >= max_jobs:
            break

        external_id = str(item.get("slug") or item.get("url") or item.get("title", ""))
        title = item.get("title") or "Unknown"
        company = item.get("company_name") or "Unknown"
        description = item.get("description") or ""
        tags = item.get("tags") or []
        location = item.get("location") or "Remote"
        job_url = item.get("url") or ""
        remote = item.get("remote", False)
        if remote and "remote" not in location.lower():
            location = f"{location} (Remote)" if location else "Remote"

        published = None
        if item.get("created_at"):
            try:
                # Unix timestamp
                published = datetime.fromtimestamp(item["created_at"])
            except Exception:
                pass

        jobs.append(Job(
            id=Job.make_id("arbeitnow", external_id),
            title=title.strip(),
            company=company.strip(),
            url=job_url,
            source="arbeitnow",
            description=description,
            location=location,
            tags=[t.lower() for t in tags if t],
            published_at=published,
            raw=item,
        ))
    return jobs