"""One-time backfill of ``expire_at`` on existing activity documents.

New activities get ``expire_at`` when they are written. Documents created before
that field existed have none, so the Firestore TTL policy would never delete
them. This script sets ``expire_at = activity_date + retention days`` on every
activity that lacks it.

It is a dry run unless ``--apply`` is given. Documents whose expiry is already
in the past will be deleted by the TTL policy shortly after they are updated.

Usage (from the repository root)::

    export GCP_PROJECT=backcountry-ski-activity-feed
    uv run python -m scripts.backfill_expire_at            # dry run
    uv run python -m scripts.backfill_expire_at --apply    # write changes
"""

import argparse
import os
import sys

from google.cloud import firestore

from src.db.activities import ACTIVITY_RETENTION_DAYS, COLLECTION_NAME, compute_expire_at

BATCH_SIZE = 400  # Firestore allows up to 500 writes per batch


def backfill(client: firestore.Client, apply: bool) -> tuple[int, int]:
    """Set ``expire_at`` on activities that lack it.

    Returns:
        A tuple of (documents examined, documents needing or receiving an update).
    """
    examined = 0
    updated = 0
    batch = client.batch()
    pending = 0

    for doc in client.collection(COLLECTION_NAME).stream():
        examined += 1
        data = doc.to_dict() or {}
        if data.get('expire_at') is not None:
            continue
        activity_date = data.get('activity_date')
        if activity_date is None:
            print(f"  skipping {doc.id}: no activity_date")
            continue

        expire_at = compute_expire_at(activity_date)
        updated += 1
        print(f"  {doc.id}: expire_at -> {expire_at.isoformat()}")
        if apply:
            batch.update(doc.reference, {'expire_at': expire_at})
            pending += 1
            if pending >= BATCH_SIZE:
                batch.commit()
                batch = client.batch()
                pending = 0

    if apply and pending:
        batch.commit()
    return examined, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--apply', action='store_true', help='write changes (default is a dry run)')
    args = parser.parse_args()

    project = os.environ.get('GCP_PROJECT', '').strip()
    if not project:
        print('GCP_PROJECT environment variable is not set.', file=sys.stderr)
        return 2

    mode = 'APPLY' if args.apply else 'DRY RUN'
    print(f"{mode}: project={project}, retention={ACTIVITY_RETENTION_DAYS} days")
    examined, updated = backfill(firestore.Client(project=project), args.apply)
    verb = 'updated' if args.apply else 'would update'
    print(f"Examined {examined} activities; {verb} {updated}.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
