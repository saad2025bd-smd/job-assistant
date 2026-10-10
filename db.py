"""JSON-based tracker for jobs and applications (lightweight & portable)."""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from base import Job


class JobDB:
    def __init__(self, db_path: str = "data/jobs.json"):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: Dict[str, Any] = {"jobs": {}, "applications": []}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {"jobs": {}, "applications": []}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def upsert_job(self, job: Job, score: float = 0.0, status: str = "discovered", save: bool = True) -> None:
        now = datetime.utcnow().isoformat()
        existing = self.data["jobs"].get(job.id, {})
        self.data["jobs"][job.id] = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "url": job.url,
            "source": job.source,
            "description": (job.description or "")[:3000],
            "location": job.location,
            "tags": job.tags,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_text": job.salary_text,
            "published_at": job.published_at.isoformat() if job.published_at else None,
            "match_score": score,
            "status": existing.get("status", status) if existing else status,
            "notes": existing.get("notes"),
            "cover_letter_path": existing.get("cover_letter_path"),
            "discovered_at": existing.get("discovered_at", now),
            "updated_at": now,
        }
        if save:
            self._save()

    def save(self) -> None:
        self._save()

    def update_status(
        self,
        job_id: str,
        status: str,
        notes: Optional[str] = None,
        cover_letter_path: Optional[str] = None,
    ) -> None:
        if job_id not in self.data["jobs"]:
            return
        job = self.data["jobs"][job_id]
        job["status"] = status
        job["updated_at"] = datetime.utcnow().isoformat()
        if notes is not None:
            job["notes"] = notes
        if cover_letter_path is not None:
            job["cover_letter_path"] = cover_letter_path
        self._save()

    def mark_applied(self, job_id: str) -> None:
        self.update_status(job_id, "applied")
        self.data["applications"].append({
            "job_id": job_id,
            "applied_at": datetime.utcnow().isoformat(),
            "status": "applied",
        })
        self._save()

    def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        jobs = list(self.data["jobs"].values())
        if status:
            jobs = [j for j in jobs if j.get("status") == status]
        jobs.sort(key=lambda j: j.get("match_score") or 0, reverse=True)
        return jobs[:limit]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.data["jobs"].get(job_id)

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for j in self.data["jobs"].values():
            s = j.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def close(self):
        pass
