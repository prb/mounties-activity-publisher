"""Data models for Mountaineers activities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


@dataclass
class Leader:
    """Represents a trip leader."""

    leader_permalink: str
    name: str

    @property
    def document_id(self) -> str:
        """Extract document ID from permalink (final path segment)."""
        return self.leader_permalink.rstrip('/').split('/')[-1]


@dataclass
class Place:
    """Represents a route or place."""

    place_permalink: str
    name: str

    @property
    def document_id(self) -> str:
        """
        Extract document ID from permalink (final two path segments with / replaced by _).

        Example:
            https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas
            -> ski-resorts-nordic-centers_snoqualmie-summit-ski-areas
        """
        parts = self.place_permalink.rstrip('/').split('/')
        return f"{parts[-2]}_{parts[-1]}"


@dataclass
class Activity:
    """Represents a Mountaineers activity."""

    activity_permalink: str
    title: str
    description: str
    difficulty_rating: list[str]
    activity_date: datetime  # stored in UTC
    place: Place
    leader: Leader
    activity_type: Optional[str] = None
    branch: Optional[str] = None
    discord_message_id: Optional[str] = None

    @property
    def document_id(self) -> str:
        """Extract document ID from permalink (final path segment)."""
        return self.activity_permalink.rstrip('/').split('/')[-1]


@dataclass
class BookkeepingStatus:
    """Represents the bookkeeping status for a function."""

    last_search_success: Optional[datetime] = None
    search_status: Optional[str] = None
    last_scrape_success: Optional[datetime] = None
    scrape_status: Optional[str] = None
    last_publish_success: Optional[datetime] = None
    publish_status: Optional[str] = None
