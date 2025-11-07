"""Discord client for publishing messages."""

import os
import requests
from datetime import datetime
from typing import Optional
import pytz

from .models import Activity


# Discord API base URL
DISCORD_API_BASE = 'https://discord.com/api/v10'

# Version for User-Agent
VERSION = os.environ.get('APP_VERSION', 'dev')
USER_AGENT = f'mounties-activities-discord-publisher/{VERSION}'

# Discord configuration (from environment variables)
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', '')
DISCORD_CHANNEL_ID = os.environ.get('DISCORD_CHANNEL_ID', '')


def get_bot_token() -> str:
    """
    Get Discord bot token from environment or Google Cloud secrets.

    Returns:
        Bot token (with whitespace stripped)

    Raises:
        ValueError: If bot token is not configured
    """
    if not DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN environment variable not set")

    # Strip whitespace/newlines that may come from Secret Manager
    return DISCORD_BOT_TOKEN.strip()


def get_channel_id() -> str:
    """
    Get Discord channel ID from environment.

    Returns:
        Channel ID

    Raises:
        ValueError: If channel ID is not configured
    """
    if not DISCORD_CHANNEL_ID:
        raise ValueError("DISCORD_CHANNEL_ID environment variable not set")

    return DISCORD_CHANNEL_ID


def format_activity_message(activity: Activity) -> str:
    """
    Format an activity as a Discord message.

    Format:
    {{activity.activity_date in YYYY-MM-DD format in Pacific timezone}}
    [{{activity.title}}]({{activity.activity_permalink}})
    led by [{{activity.leader.name}}](<{{activity.leader.leader_permalink}}>)
    at [{{activity.place.name}}](<{{activity.place.place_permalink}}>)

    Note: Using [text](<url>) prevents Discord from rendering link previews.

    Args:
        activity: Activity object to format

    Returns:
        Formatted message string

    Example:
        >>> from models import Activity, Leader, Place
        >>> from datetime import datetime
        >>> import pytz
        >>> leader = Leader(
        ...     leader_permalink="https://www.mountaineers.org/members/john-doe",
        ...     name="John Doe"
        ... )
        >>> place = Place(
        ...     place_permalink="https://www.mountaineers.org/routes/mount-rainier",
        ...     name="Mount Rainier"
        ... )
        >>> activity = Activity(
        ...     activity_permalink="https://www.mountaineers.org/activities/climb",
        ...     title="Climb Mount Rainier",
        ...     description="Summit climb",
        ...     difficulty_rating=["Intermediate"],
        ...     activity_date=datetime(2026, 7, 4, 14, 0, 0, tzinfo=pytz.UTC),
        ...     leader=leader,
        ...     place=place
        ... )
        >>> msg = format_activity_message(activity)
        >>> '2026-07-04' in msg
        True
        >>> '[Climb Mount Rainier]' in msg
        True
    """
    # Convert activity date from UTC to Pacific time
    pacific = pytz.timezone('America/Los_Angeles')
    pacific_date = activity.activity_date.astimezone(pacific)
    date_str = pacific_date.strftime('%Y-%m-%d')

    # Format message
    message = (
        f"{date_str} "
        f"[{activity.title}]({activity.activity_permalink}) "
        f"led by [{activity.leader.name}](<{activity.leader.leader_permalink}>) "
        f"at [{activity.place.name}](<{activity.place.place_permalink}>)"
    )

    return message


def send_discord_message(content: str, channel_id: Optional[str] = None, bot_token: Optional[str] = None) -> str:
    """
    Send a message to a Discord channel.

    Args:
        content: Message content to send
        channel_id: Discord channel ID (uses DISCORD_CHANNEL_ID env var if not provided)
        bot_token: Discord bot token (uses DISCORD_BOT_TOKEN env var if not provided)

    Returns:
        Discord message ID

    Raises:
        ValueError: If channel_id or bot_token not provided and not in environment
        requests.exceptions.HTTPError: If Discord API request fails

    Example:
        >>> # With environment variables set
        >>> message_id = send_discord_message("Hello, Discord!")
        >>> len(message_id) > 0
        True
    """
    # Get configuration
    if channel_id is None:
        channel_id = get_channel_id()

    if bot_token is None:
        bot_token = get_bot_token()

    # Construct API URL
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"

    # Set headers
    headers = {
        'Authorization': f'Bot {bot_token}',
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
    }

    # Construct payload
    payload = {
        'content': content,
    }

    # Send request
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    # Extract message ID from response
    response_data = response.json()
    message_id = response_data['id']

    return message_id


def publish_activity_to_discord(activity: Activity, channel_id: Optional[str] = None, bot_token: Optional[str] = None) -> str:
    """
    Publish an activity to Discord.

    Args:
        activity: Activity to publish
        channel_id: Discord channel ID (optional, uses env var if not provided)
        bot_token: Discord bot token (optional, uses env var if not provided)

    Returns:
        Discord message ID

    Raises:
        ValueError: If channel_id or bot_token not configured
        requests.exceptions.HTTPError: If Discord API request fails

    Example:
        >>> message_id = publish_activity_to_discord(activity)
        >>> len(message_id) > 0
        True
    """
    # Format message
    content = format_activity_message(activity)

    # Send to Discord
    message_id = send_discord_message(content, channel_id=channel_id, bot_token=bot_token)

    return message_id
