from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import get_settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(get_settings().mongodb_uri, serverSelectionTimeoutMS=2000)
    return _client


def set_client(client: MongoClient | None) -> None:
    global _client
    _client = client


def get_db() -> Database:
    return get_client()[get_settings().mongo_db]
