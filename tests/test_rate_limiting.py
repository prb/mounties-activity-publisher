"""Tests for 429 handling: Discord Retry-After retries and the Yellow status."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from hypothesis import given, strategies as st

from src import discord_client
from src.discord_client import (
    MAX_RATE_LIMIT_WAIT_SECONDS,
    MAX_SEND_ATTEMPTS,
    DiscordRateLimitError,
    _retry_after_seconds,
    send_discord_message,
)
from src.functions import publisher, searcher


def _response(status: int, retry_after=None, body=None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.headers = {'Retry-After': str(retry_after)} if retry_after is not None else {}
    response.json.return_value = body if body is not None else {'id': '42'}
    return response


@pytest.fixture
def post(mocker) -> MagicMock:
    return mocker.patch('src.discord_client.requests.post')


@pytest.fixture
def sleep(mocker) -> MagicMock:
    return mocker.patch('src.discord_client.time.sleep')


def _send() -> str:
    return send_discord_message('hello', channel_id='1', bot_token='token')


def test_retries_after_429_using_retry_after(post, sleep) -> None:
    post.side_effect = [_response(429, 2), _response(200)]

    assert _send() == '42'

    sleep.assert_called_once_with(2.0)
    assert post.call_count == 2


def test_gives_up_immediately_when_retry_after_exceeds_budget(post, sleep) -> None:
    post.side_effect = [_response(429, MAX_RATE_LIMIT_WAIT_SECONDS + 1)]

    with pytest.raises(DiscordRateLimitError) as excinfo:
        _send()

    assert excinfo.value.retry_after == MAX_RATE_LIMIT_WAIT_SECONDS + 1
    sleep.assert_not_called()
    assert post.call_count == 1


def test_stops_after_max_attempts(post, sleep) -> None:
    post.side_effect = [_response(429, 1)] * 10

    with pytest.raises(DiscordRateLimitError):
        _send()

    assert post.call_count == MAX_SEND_ATTEMPTS
    assert sleep.call_count == MAX_SEND_ATTEMPTS - 1


@given(st.lists(st.floats(min_value=0, max_value=60, allow_nan=False), min_size=1, max_size=10))
def test_total_wait_and_attempts_are_bounded(retry_afters: list[float]) -> None:
    """For any sequence of 429s, waiting stays within budget and attempts are capped."""
    waits: list[float] = []
    responses = [_response(429, value) for value in retry_afters] + [_response(200)]
    with patch.object(discord_client.requests, 'post', side_effect=responses) as post, \
            patch.object(discord_client.time, 'sleep', side_effect=waits.append):
        try:
            _send()
        except DiscordRateLimitError:
            pass
        assert sum(waits) <= MAX_RATE_LIMIT_WAIT_SECONDS
        assert post.call_count <= MAX_SEND_ATTEMPTS


def test_retry_after_falls_back_to_json_body() -> None:
    assert _retry_after_seconds(_response(429, None, {'retry_after': 1.5})) == 1.5


def test_retry_after_defaults_when_missing() -> None:
    assert _retry_after_seconds(_response(429, None, {})) == 1.0


def test_non_429_errors_are_not_retried(post, sleep) -> None:
    response = _response(500)
    response.raise_for_status.side_effect = requests.exceptions.HTTPError('server error')
    post.side_effect = [response]

    with pytest.raises(requests.exceptions.HTTPError):
        _send()

    sleep.assert_not_called()
    assert post.call_count == 1


def test_publisher_records_yellow_when_rate_limited(mocker) -> None:
    activity = MagicMock(discord_message_id=None)
    mocker.patch.object(publisher, 'get_activity', return_value=activity)
    mocker.patch.object(publisher, 'publish_activity_to_discord', side_effect=DiscordRateLimitError(5))
    update_status = mocker.patch.object(publisher, 'update_publish_status')

    result = publisher.publisher_handler('some-activity')

    assert result['status'] == 'error'
    update_status.assert_called_once_with('Yellow: Backing off.')


def _http_error(status: int) -> requests.exceptions.HTTPError:
    error = requests.exceptions.HTTPError('boom')
    error.response = MagicMock(status_code=status)
    return error


@pytest.mark.parametrize(
    'status, expected_status',
    [(429, 'Yellow: Backing off.'), (500, 'Red: boom')],
)
def test_searcher_status_for_http_errors(mocker, status: int, expected_status: str) -> None:
    mocker.patch.object(searcher, 'is_processing_enabled', return_value=True)
    mocker.patch.object(searcher, 'fetch_search_results', side_effect=_http_error(status))
    update_status = mocker.patch.object(searcher, 'update_search_status')

    result = searcher.searcher_handler()

    assert result['status'] == 'error'
    update_status.assert_called_once_with(expected_status)
