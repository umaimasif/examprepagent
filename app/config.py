"""Central configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# Groq
GROQ_API_KEY = _get("GROQ_API_KEY")
GROQ_CHAT_MODEL = _get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
GROQ_WHISPER_MODEL = _get("GROQ_WHISPER_MODEL", "whisper-large-v3")

# MongoDB
MONGODB_URI = _get("MONGODB_URI")
MONGODB_DB = _get("MONGODB_DB", "examprep")

# Embeddings
EMBEDDINGS_PROVIDER = _get("EMBEDDINGS_PROVIDER", "jina")
JINA_API_KEY = _get("JINA_API_KEY")
JINA_MODEL = _get("JINA_MODEL", "jina-embeddings-v3")
EMBEDDING_DIM = int(_get("EMBEDDING_DIM", "1024"))

# Atlas Vector Search index name (create this in Atlas UI)
VECTOR_INDEX_NAME = _get("VECTOR_INDEX_NAME", "vector_index")
