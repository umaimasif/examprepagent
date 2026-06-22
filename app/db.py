"""MongoDB Atlas connection and collection helpers.

Collections:
  - lectures : one doc per processed YouTube lecture (transcript, notes, questions)
  - chunks   : RAG chunks with embeddings (vector-indexed)
  - attempts : quiz attempts / scores for progress tracking
"""
from functools import lru_cache

from pymongo import MongoClient

from app import config


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    if not config.MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not set")
    return MongoClient(config.MONGODB_URI, appname="examprep")


def get_db():
    return get_client()[config.MONGODB_DB]


def lectures():
    return get_db()["lectures"]


def chunks():
    return get_db()["chunks"]


def attempts():
    return get_db()["attempts"]
