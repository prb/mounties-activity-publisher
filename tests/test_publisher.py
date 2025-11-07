"""Tests for Publisher function and Discord client."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
import pytz

from src.models import Activity, Leader, Place
from src.discord_client import (
    format_activity_message,
    send_discord_message,
    publish_activity_to_discord,
)
from src.functions.publisher import publisher_handler


@pytest.fixture
def sample_leader():
    """Create a sample leader."""
    return Leader(
        leader_permalink="https://www.mountaineers.org/members/randy-oakley",
        name="Randy Oakley"
    )


@pytest.fixture
def sample_place():
    """Create a sample place."""
    return Place(
        place_permalink="https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas",
        name="Snoqualmie Summit Ski Areas"
    )


@pytest.fixture
def sample_activity(sample_leader, sample_place):
    """Create a sample activity."""
    return Activity(
        activity_permalink="https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10",
        title="Backcountry Ski/Snowboard - Snoqualmie Summit West",
        description="Tuesday night headlamp workout series for backcountry skiers / splitboarders.",
        difficulty_rating=["M1 Intermediate Ski"],
        activity_date=datetime(2026, 2, 10, 8, 0, 0, tzinfo=pytz.UTC),  # 8am UTC = midnight Pacific
        leader=sample_leader,
        place=sample_place,
    )


# Discord Client Tests

def test_format_activity_message(sample_activity):
    """Test formatting an activity message for Discord."""
    message = format_activity_message(sample_activity)

    # Check date is in Pacific timezone
    assert message.startswith('2026-02-10 ')  # Feb 10 midnight in Pacific

    # Check title with link (no preview)
    assert '[Backcountry Ski/Snowboard - Snoqualmie Summit West](https://www.mountaineers.org/activities/activities/backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10)' in message

    # Check leader with no-preview link syntax
    assert 'led by [Randy Oakley](<https://www.mountaineers.org/members/randy-oakley>)' in message

    # Check place with no-preview link syntax
    assert 'at [Snoqualmie Summit Ski Areas](<https://www.mountaineers.org/activities/routes-places/ski-resorts-nordic-centers/snoqualmie-summit-ski-areas>)' in message


def test_format_activity_message_date_conversion():
    """Test that UTC date is correctly converted to Pacific time."""
    leader = Leader(
        leader_permalink="https://www.mountaineers.org/members/test",
        name="Test Leader"
    )
    place = Place(
        place_permalink="https://www.mountaineers.org/routes/test",
        name="Test Place"
    )

    # Create activity with specific UTC time
    # Feb 10, 2026 at 2pm UTC = 6am Pacific (same day)
    activity = Activity(
        activity_permalink="https://www.mountaineers.org/activities/test",
        title="Test Activity",
        description="Test",
        difficulty_rating=["Easy"],
        activity_date=datetime(2026, 2, 10, 14, 0, 0, tzinfo=pytz.UTC),
        leader=leader,
        place=place,
    )

    message = format_activity_message(activity)
    assert message.startswith('2026-02-10 ')


def test_send_discord_message_success(mocker):
    """Test successful Discord message send."""
    # Mock requests.post
    mock_response = MagicMock()
    mock_response.json.return_value = {'id': '1234567890123456'}
    mock_response.raise_for_status = MagicMock()

    mock_post = mocker.patch('src.discord_client.requests.post')
    mock_post.return_value = mock_response

    # Mock environment variables
    mocker.patch('src.discord_client.DISCORD_BOT_TOKEN', 'test_bot_token')
    mocker.patch('src.discord_client.DISCORD_CHANNEL_ID', 'test_channel_id')

    # Send message
    message_id = send_discord_message(
        "Test message",
        channel_id='test_channel_id',
        bot_token='test_bot_token'
    )

    # Verify
    assert message_id == '1234567890123456'

    # Verify API call
    mock_post.assert_called_once()

    # Get call arguments
    call_kwargs = mock_post.call_args.kwargs
    call_args_list = mock_post.call_args.args

    # Check URL (first positional argument)
    assert call_args_list[0] == 'https://discord.com/api/v10/channels/test_channel_id/messages'

    # Check headers
    headers = call_kwargs['headers']
    assert headers['Authorization'] == 'Bot test_bot_token'
    assert headers['Content-Type'] == 'application/json'
    assert 'mounties-activities-discord-publisher' in headers['User-Agent']

    # Check payload
    payload = call_kwargs['json']
    assert payload['content'] == 'Test message'


def test_send_discord_message_missing_channel_id(mocker):
    """Test that missing channel ID raises error."""
    mocker.patch('src.discord_client.DISCORD_CHANNEL_ID', '')

    with pytest.raises(ValueError, match="DISCORD_CHANNEL_ID"):
        send_discord_message("Test", bot_token='test_token')


def test_send_discord_message_missing_bot_token(mocker):
    """Test that missing bot token raises error."""
    mocker.patch('src.discord_client.DISCORD_BOT_TOKEN', '')

    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        send_discord_message("Test", channel_id='test_channel')


def test_publish_activity_to_discord(mocker, sample_activity):
    """Test publishing an activity to Discord."""
    # Mock send_discord_message
    mock_send = mocker.patch('src.discord_client.send_discord_message')
    mock_send.return_value = '9876543210987654'

    # Publish activity
    message_id = publish_activity_to_discord(
        sample_activity,
        channel_id='test_channel',
        bot_token='test_token'
    )

    # Verify
    assert message_id == '9876543210987654'

    # Verify send_discord_message was called with formatted message
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    content = call_args[0][0]

    # Check formatted content
    assert '2026-02-10' in content
    assert 'Backcountry Ski/Snowboard - Snoqualmie Summit West' in content
    assert 'Randy Oakley' in content
    assert 'Snoqualmie Summit Ski Areas' in content


# Publisher Function Tests

def test_publisher_handler_success(mocker, sample_activity):
    """Test successful publishing of activity."""
    # Mock get_activity
    mock_get_activity = mocker.patch('src.functions.publisher.get_activity')
    mock_get_activity.return_value = sample_activity

    # Mock publish_activity_to_discord
    mock_publish = mocker.patch('src.functions.publisher.publish_activity_to_discord')
    mock_publish.return_value = '1234567890123456'

    # Mock update_discord_message_id
    mock_update = mocker.patch('src.functions.publisher.update_discord_message_id')

    # Call handler
    result = publisher_handler({
        'activity_id': 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    })

    # Verify result
    assert result['status'] == 'success'
    assert result['message_id'] == '1234567890123456'

    # Verify calls
    mock_get_activity.assert_called_once_with('backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10')
    mock_publish.assert_called_once_with(sample_activity)
    mock_update.assert_called_once_with('backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10', '1234567890123456')


def test_publisher_handler_already_published(mocker, sample_activity):
    """Test that publisher skips already-published activities."""
    # Set discord_message_id to simulate already published
    sample_activity.discord_message_id = '9999999999999999'

    # Mock get_activity
    mock_get_activity = mocker.patch('src.functions.publisher.get_activity')
    mock_get_activity.return_value = sample_activity

    # Mock publish (should not be called)
    mock_publish = mocker.patch('src.functions.publisher.publish_activity_to_discord')

    # Call handler
    result = publisher_handler({
        'activity_id': 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    })

    # Verify result
    assert result['status'] == 'skipped'
    assert result['message_id'] == '9999999999999999'
    assert 'already published' in result['reason']

    # Verify publish was not called
    mock_publish.assert_not_called()


def test_publisher_handler_missing_activity_id(mocker):
    """Test that publisher returns error if activity_id is missing."""
    result = publisher_handler({})

    assert result['status'] == 'error'
    assert 'Missing required parameter' in result['error']


def test_publisher_handler_activity_not_found(mocker):
    """Test that publisher returns error if activity not found."""
    # Mock get_activity to return None
    mock_get_activity = mocker.patch('src.functions.publisher.get_activity')
    mock_get_activity.return_value = None

    # Call handler
    result = publisher_handler({
        'activity_id': 'nonexistent-activity'
    })

    # Verify result
    assert result['status'] == 'error'
    assert 'Activity not found' in result['error']


def test_publisher_handler_discord_error(mocker, sample_activity):
    """Test that publisher handles Discord API errors."""
    # Mock get_activity
    mock_get_activity = mocker.patch('src.functions.publisher.get_activity')
    mock_get_activity.return_value = sample_activity

    # Mock publish to raise exception
    mock_publish = mocker.patch('src.functions.publisher.publish_activity_to_discord')
    mock_publish.side_effect = Exception('Discord API error')

    # Call handler
    result = publisher_handler({
        'activity_id': 'backcountry-ski-snowboard-snoqualmie-summit-west-2-2026-02-10'
    })

    # Verify error response
    assert result['status'] == 'error'
    assert 'Discord API error' in result['error']
