from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CommitInfo:
    hash: str
    short_hash: str
    message: str
    author: str
    date: datetime
    is_pushed: bool
    changed_files: list[str]

    @property
    def relative_time(self) -> str:
        now = datetime.now(timezone.utc)
        # ensure date is tz-aware
        date = self.date
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        delta = now - date
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        if days < 30:
            return f"{days}d"
        months = days // 30
        if months < 12:
            return f"{months}mo"
        return f"{days // 365}y"

    @property
    def summary_line(self) -> str:
        """Single-line display: short_hash  message  author  relative_time"""
        msg = self.message.splitlines()[0][:60]
        return f"{self.short_hash}  {msg:<60}  {self.author:<20}  {self.relative_time}"


@dataclass
class BranchInfo:
    name: str
    is_local: bool
    is_current: bool
    remote: Optional[str] = None

    @property
    def display_name(self) -> str:
        prefix = "● " if self.is_current else "  "
        return f"{prefix}{self.name}"
