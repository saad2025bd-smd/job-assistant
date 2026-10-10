from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import hashlib


@dataclass
class Job:
    """Normalized job posting."""
    id: str
    title: str
    company: str
    url: str
    source: str
    description: str = ""
    location: str = "Remote"
    tags: List[str] = field(default_factory=list)
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"
    salary_text: str = ""
    published_at: Optional[datetime] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def make_id(source: str, external_id: str) -> str:
        return hashlib.sha256(f"{source}:{external_id}".encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "source": self.source,
            "description": self.description,
            "location": self.location,
            "tags": self.tags,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "salary_text": self.salary_text,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }