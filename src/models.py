"""Data models for Mountaineers activities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
    discord_message_id: Optional[str] = None

    @property
    def document_id(self) -> str:
        """Extract document ID from permalink (final path segment)."""
        return self.activity_permalink.rstrip('/').split('/')[-1]
