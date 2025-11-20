import unittest
from unittest.mock import MagicMock, patch
from src.models import Activity, Leader, Place
from src.db.activities import create_activity
from datetime import datetime
import pytz

class TestTransactionalActivityCreation(unittest.TestCase):

    @patch('src.db.activities.get_firestore_client')
    def test_create_activity_with_transaction(self, mock_get_client):
        # Setup
        mock_db = MagicMock()
        mock_get_client.return_value = mock_db
        
        mock_transaction = MagicMock()
        
        # Mock document reference and snapshot
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_snapshot
        
        # Create dummy activity
        leader = Leader(leader_permalink="http://leader", name="Leader")
        place = Place(place_permalink="http://place", name="Place")
        activity = Activity(
            activity_permalink="http://activity",
            title="Test Activity",
            description="Desc",
            difficulty_rating=["M1"],
            activity_date=datetime.now(pytz.UTC),
            leader=leader,
            place=place,
            activity_type="Skiing"
        )
        
        # Execute
        create_activity(activity, transaction=mock_transaction)
        
        # Verify transaction usage
        mock_doc_ref.get.assert_called_with(transaction=mock_transaction)
        mock_transaction.set.assert_called_once()
        
    @patch('src.db.activities.get_firestore_client')
    def test_create_activity_exists_in_transaction(self, mock_get_client):
        # Setup
        mock_db = MagicMock()
        mock_get_client.return_value = mock_db
        
        mock_transaction = MagicMock()
        
        # Mock document reference and snapshot
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True # Simulating existing document
        mock_doc_ref.get.return_value = mock_snapshot
        
        # Create dummy activity
        leader = Leader(leader_permalink="http://leader", name="Leader")
        place = Place(place_permalink="http://place", name="Place")
        activity = Activity(
            activity_permalink="http://activity",
            title="Test Activity",
            description="Desc",
            difficulty_rating=["M1"],
            activity_date=datetime.now(pytz.UTC),
            leader=leader,
            place=place,
            activity_type="Skiing"
        )
        
        # Execute & Verify
        with self.assertRaises(ValueError) as cm:
            create_activity(activity, transaction=mock_transaction)
            
        self.assertIn("already exists", str(cm.exception))
        mock_doc_ref.get.assert_called_with(transaction=mock_transaction)
        mock_transaction.set.assert_not_called()

if __name__ == '__main__':
    unittest.main()
