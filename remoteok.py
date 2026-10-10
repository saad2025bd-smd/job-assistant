import requests
from datetime import datetime
from typing import List
from base import Job


def fetch_jobs(max_jobs: int = 50) -> List[Job]:
    """Fetch jobs from RemoteOK public API (no key required)."""
    url = "https://remoteok.com/api"
    headers = {
        "User-Agent": "JobAssistant/1.0 (personal job search tool)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[RemoteOK] Error: {e}")
        return []

    jobs: List[Job] = []
    # First element is often a legal notice
    for item in data:
        if not isinstance(item, dict) or "id" not in item:
            continue
        if len(jobs) >= max_jobs:
            break

        external_id = str(item.get("id") or item.get("slug") or item.get("url", ""))
        title = item.get("position") or item.get("title") or "Unknown"
        company = item.get("company") or "Unknown"
        description = item.get("description") or ""
        tags = item.get("tags") or []
        location = item.get("location") or "Remote"
        url = item.get("url") or item.get("apply_url") or f"https://remoteok.com/remote-jobs/{external_id}"

        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        try:
            salary_min = float(salary_min) if salary_min else None
            salary_max = float(salary_max) if salary_max else None
        except (TypeError, ValueError):
            salary_min = salary_max = None

        published = None
        if item.get("date"):
            try:
                published = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
            except Exception:
                pass

        jobs.append(Job(
            id=Job.make_id("remoteok", external_id),
            title=title.strip(),
            company=company.strip(),
            url=url,
            source="remoteok",
            description=description,
            location=location,
            tags=[t.lower() for t in tags if t],
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD",
            published_at=published,
            raw=item,
        ))
    return jobs