"""Firestore client initialization and management."""

import os
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client


_firestore_client: Optional[Client] = None


def initialize_firebase(use_emulator: bool = False) -> None:
    """
    Initialize Firebase Admin SDK.

    Args:
        use_emulator: If True, configure to use Firestore emulator

    Note:
        For production, expects GOOGLE_APPLICATION_CREDENTIALS env var to be set.
        For emulator, expects FIRESTORE_EMULATOR_HOST env var (e.g., localhost:8080).
    """
    global _firestore_client

    if firebase_admin._apps:
        # Already initialized
        return

    if use_emulator:
        # Use emulator - no credentials needed
        os.environ.setdefault('FIRESTORE_EMULATOR_HOST', 'localhost:8080')
        firebase_admin.initialize_app()
    else:
        # Production - use application default credentials or service account
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)

    _firestore_client = firestore.client()


def get_firestore_client() -> Client:
    """
    Get the Firestore client instance.

    Returns:
        Firestore client

    Raises:
        RuntimeError: If Firebase has not been initialized
    """
    global _firestore_client

    if _firestore_client is None:
        raise RuntimeError(
            "Firestore client not initialized. Call initialize_firebase() first."
        )

    return _firestore_client
