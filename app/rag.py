"""Step 4 - RAG tutor. Chunk the transcript, embed + store chunks in MongoDB,
retrieve via Atlas Vector Search, and answer using ONLY retrieved context.

Requires an Atlas Vector Search index named by VECTOR_INDEX_NAME on the
`chunks` collection (see README for the index JSON)."""
from typing import List

from app import config, db, embeddings, llm


def chunk_text(text: str, size: int = 1200, overlap: int = 200) -> List[str]:
    text = " ".join(text.split())
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if c.strip()]


def index_lecture(lecture_id: str, transcript: str) -> int:
    """Embed and store transcript chunks. Returns number of chunks stored."""
    db.chunks().delete_many({"lecture_id": lecture_id})
    pieces = chunk_text(transcript)
    vectors = embeddings.embed(pieces, is_query=False)
    docs = [
        {
            "lecture_id": lecture_id,
            "chunk_index": i,
            "text": piece,
            "embedding": vec,
        }
        for i, (piece, vec) in enumerate(zip(pieces, vectors))
    ]
    if docs:
        db.chunks().insert_many(docs)
    return len(docs)


def retrieve(lecture_id: str, question: str, top_k: int = 5) -> List[dict]:
    qvec = embeddings.embed_one(question, is_query=True)
    pipeline = [
        {
            "$vectorSearch": {
                "index": config.VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": qvec,
                "numCandidates": max(top_k * 20, 100),
                "limit": top_k,
                "filter": {"lecture_id": lecture_id},
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "chunk_index": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(db.chunks().aggregate(pipeline))


TUTOR_SYSTEM = (
    "You are a study tutor. Answer the student's question using ONLY the lecture "
    "context provided. If the answer is not in the context, say you could not "
    "find it in this lecture. Be clear and concise; use examples from the context."
)


def answer(lecture_id: str, question: str, top_k: int = 5) -> dict:
    hits = retrieve(lecture_id, question, top_k)
    context = "\n\n".join(f"[chunk {h['chunk_index']}] {h['text']}" for h in hits)
    if not context:
        return {"answer": "No indexed content found for this lecture.", "sources": []}
    reply = llm.chat(
        TUTOR_SYSTEM,
        f"LECTURE CONTEXT:\n{context}\n\nSTUDENT QUESTION: {question}",
        temperature=0.2,
    )
    return {"answer": reply, "sources": [h["chunk_index"] for h in hits]}
