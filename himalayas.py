import requests
from datetime import datetime
from typing import List, Optional
from base import Job


def fetch_jobs(search: Optional[str] = None, max_jobs: int = 40) -> List[Job]:
    """Fetch remote jobs from Himalayas public API (no key)."""
    headers = {"User-Agent": "JobAssistant/2.0 (personal job search)"}
    jobs: List[Job] = []

    try:
        if search:
            url = "https://himalayas.app/jobs/api/search"
            params = {"q": search, "limit": min(max_jobs, 20)}
        else:
            url = "https://himalayas.app/jobs/api"
            params = {"limit": min(max_jobs, 20)}

        resp = requests.get(url, params=params, headers=headers, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Himalayas] Error: {e}")
        return []

    # Response shapes vary: list under "jobs" or "data"
    items = data.get("jobs") or data.get("data") or []
    if isinstance(data, list):
        items = data

    for item in items:
        if len(jobs) >= max_jobs:
            break
        if not isinstance(item, dict):
            continue

        external_id = str(item.get("guid") or item.get("id") or item.get("applicationLink") or item.get("title", ""))
        title = item.get("title") or "Unknown"
        company = item.get("companyName") or item.get("company") or "Unknown"
        description = item.get("description") or item.get("excerpt") or ""
        if description and "<" in description:
            import re
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()

        tags = []
        for key in ("categories", "parentCategories", "seniority"):
            val = item.get(key)
            if isinstance(val, list):
                tags.extend([str(x).lower() for x in val])
            elif val:
                tags.append(str(val).lower())
        if item.get("employmentType"):
            tags.append(str(item["employmentType"]).lower())

        locs = item.get("locationRestrictions") or []
        if isinstance(locs, list) and locs:
            # may be list of dicts or strings
            loc_parts = []
            for loc in locs[:3]:
                if isinstance(loc, dict):
                    loc_parts.append(loc.get("name") or loc.get("country") or str(loc))
                else:
                    loc_parts.append(str(loc))
            location = ", ".join(loc_parts) if loc_parts else "Remote"
        else:
            location = "Remote / Worldwide"

        job_url = item.get("applicationLink") or item.get("url") or item.get("guid") or ""

        salary_min = item.get("minSalary")
        salary_max = item.get("maxSalary")
        try:
            salary_min = float(salary_min) if salary_min is not None else None
            salary_max = float(salary_max) if salary_max is not None else None
        except (TypeError, ValueError):
            salary_min = salary_max = None

        currency = item.get("currency") or "USD"
        published = None
        pub = item.get("pubDate")
        if pub:
            try:
                if isinstance(pub, (int, float)):
                    # ms timestamp
                    published = datetime.utcfromtimestamp(pub / 1000 if pub > 1e12 else pub)
                else:
                    published = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
            except Exception:
                pass

        jobs.append(Job(
            id=Job.make_id("himalayas", external_id),
            title=str(title).strip(),
            company=str(company).strip(),
            url=job_url,
            source="himalayas",
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
