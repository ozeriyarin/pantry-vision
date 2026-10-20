"""Photos to the private bucket under photos/, which a 30-day lifecycle rule deletes (FR-012)."""

from datetime import datetime
from uuid import uuid4


def photo_path(now: datetime) -> str:
    return f"photos/{now:%Y/%m/%d}/{uuid4().hex}.jpg"


class GcsBlob:
    def __init__(self, bucket_name: str, client=None):
        from google.cloud import storage

        self._bucket = (client or storage.Client()).bucket(bucket_name)

    def put_photo(self, data: bytes, now: datetime) -> str:
        path = photo_path(now)
        self._bucket.blob(path).upload_from_string(data, content_type="image/jpeg")
        return path
