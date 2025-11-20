"""Tests for publishing catchup functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.functions.catchup import publishing_catchup_handler


@patch('src.functions.catchup.enqueue_publish_task')
@patch('src.functions.catchup.get_unpublished_activity_ids')
def test_catchup_handler_success(mock_get_ids, mock_enqueue):
    """Test successful catchup with multiple unpublished activities."""
    # Arrange
    mock_get_ids.return_value = ['activity1', 'activity2', 'activity3']
    mock_enqueue.return_value = None

    # Act
    result = publishing_catchup_handler()

    # Assert
    assert result['status'] == 'success'
    assert result['activities_found'] == 3
    assert result['tasks_enqueued'] == 3
    assert mock_get_ids.call_count == 1
    assert mock_enqueue.call_count == 3


@patch('src.functions.catchup.enqueue_publish_task')
@patch('src.functions.catchup.get_unpublished_activity_ids')
def test_catchup_handler_no_unpublished(mock_get_ids, mock_enqueue):
    """Test catchup when no unpublished activities exist."""
    # Arrange
    mock_get_ids.return_value = []

    # Act
    result = publishing_catchup_handler()

    # Assert
    assert result['status'] == 'success'
    assert result['activities_found'] == 0
    assert result['tasks_enqueued'] == 0
    assert mock_get_ids.call_count == 1
    assert mock_enqueue.call_count == 0


@patch('src.functions.catchup.enqueue_publish_task')
@patch('src.functions.catchup.get_unpublished_activity_ids')
def test_catchup_handler_partial_failure(mock_get_ids, mock_enqueue):
    """Test catchup continues when some enqueues fail."""
    # Arrange
    mock_get_ids.return_value = ['activity1', 'activity2', 'activity3']
    
    # Make enqueue fail for the second activity
    def enqueue_side_effect(activity_id):
        if activity_id == 'activity2':
            raise Exception("Enqueue failed")
    
    mock_enqueue.side_effect = enqueue_side_effect

    # Act
    result = publishing_catchup_handler()

    # Assert
    assert result['status'] == 'success'
    assert result['activities_found'] == 3
    assert result['tasks_enqueued'] == 2  # Only 2 succeeded
    assert mock_enqueue.call_count == 3


@patch('src.functions.catchup.enqueue_publish_task')
@patch('src.functions.catchup.get_unpublished_activity_ids')
def test_catchup_handler_query_failure(mock_get_ids, mock_enqueue):
    """Test catchup handles query failures gracefully."""
    # Arrange
    mock_get_ids.side_effect = Exception("Firestore query failed")

    # Act
    result = publishing_catchup_handler()

    # Assert
    assert result['status'] == 'error'
    assert 'error' in result
    assert 'Firestore query failed' in result['error']
    assert mock_enqueue.call_count == 0


@patch('src.db.activities.get_firestore_client')
def test_get_unpublished_activity_ids_integration(mock_get_client):
    """Test get_unpublished_activity_ids query construction."""
    from src.db.activities import get_unpublished_activity_ids
    
    # Arrange
    mock_db = Mock()
    mock_collection = Mock()
    mock_query = Mock()
    mock_docs = [Mock(id='act1'), Mock(id='act2')]
    
    mock_get_client.return_value = mock_db
    mock_db.collection.return_value = mock_collection
    mock_collection.where.return_value = mock_query
    mock_query.stream.return_value = iter(mock_docs)

    # Act
    result = get_unpublished_activity_ids()

    # Assert
    assert result == ['act1', 'act2']
    mock_db.collection.assert_called_once_with('activities')
    # Verify it uses positional arguments (the fix from issue #8)
    mock_collection.where.assert_called_once_with(
        field_path='discord_message_id',
        op_string='==',
        value=None
    )
