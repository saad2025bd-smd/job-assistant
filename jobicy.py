import requests
from datetime import datetime
from typing import List, Optional
from base import Job


def fetch_jobs(search: Optional[str] = None, max_jobs: int = 40) -> List[Job]:
    """Fetch remote jobs from Jobicy public API (no key)."""
    url = "https://jobicy.com/api/v2/remote-jobs"
    params = {"count": min(max_jobs, 100)}
    if search:
        params["tag"] = search

    headers = {"User-Agent": "JobAssistant/2.0 (personal job search)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Jobicy] Error: {e}")
        return []

    jobs: List[Job] = []
    for item in data.get("jobs", []):
        if len(jobs) >= max_jobs:
            break
        external_id = str(item.get("id") or item.get("jobSlug") or item.get("url", ""))
        title = item.get("jobTitle") or "Unknown"
        company = item.get("companyName") or "Unknown"
        description = item.get("jobDescription") or item.get("jobExcerpt") or ""
        # strip simple HTML tags
        if description and "<" in description:
            import re
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()

        tags = []
        ind = item.get("jobIndustry")
        if isinstance(ind, list):
            tags.extend([str(x).lower() for x in ind])
        elif ind:
            tags.append(str(ind).lower())
        if item.get("jobType"):
            tags.append(str(item["jobType"]).lower())
        if item.get("jobLevel"):
            tags.append(str(item["jobLevel"]).lower())

        location = item.get("jobGeo") or "Remote"
        job_url = item.get("url") or ""

        salary_min = item.get("annualSalaryMin")
        salary_max = item.get("annualSalaryMax")
        try:
            salary_min = float(salary_min) if salary_min else None
            salary_max = float(salary_max) if salary_max else None
        except (TypeError, ValueError):
            salary_min = salary_max = None

        currency = item.get("salaryCurrency") or "USD"
        published = None
        if item.get("pubDate"):
            try:
                published = datetime.fromisoformat(str(item["pubDate"]).replace("Z", "+00:00"))
            except Exception:
                pass

        jobs.append(Job(
            id=Job.make_id("jobicy", external_id),
            title=title.strip(),
            company=company.strip(),
            url=job_url,
            source="jobicy",
            description=description,
            location=location,
            tags=tags,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            published_at=published,
            raw=item,
        ))
    return jobs
