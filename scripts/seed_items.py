"""Push config/items.yaml to Firestore without a deploy (needs gcloud application-default credentials)."""

from pantry.adapters.firestore_store import FirestoreStore
from pantry.config import ROOT
from pantry.domain.items import load_item_types, seed_item_types

if __name__ == "__main__":
    written = seed_item_types(FirestoreStore(), load_item_types(ROOT / "config/items.yaml"))
    print(f"item types written: {written}")
