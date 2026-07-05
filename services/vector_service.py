import chromadb
from chromadb.config import Settings
import os

# Initialize ChromaDB with persistent local storage
chroma_client = chromadb.PersistentClient(
    path="./chromadb_data"
)

COLLECTION_NAME = "worker_profiles"

def get_collection():
    return chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

class VectorService:

    @staticmethod
    def get_doc_id(worker_id: str) -> str:
        return f"worker_{worker_id}"

    @staticmethod
    def is_worker_indexed(worker_id: str) -> bool:
        collection = get_collection()
        try:
            result = collection.get(ids=[VectorService.get_doc_id(worker_id)])
            return len(result["ids"]) > 0
        except Exception:
            return False

    @staticmethod
    def index_worker(worker_id: str, chunks: list[str], metadata: dict):
        collection = get_collection()
        doc_id = VectorService.get_doc_id(worker_id)

        # Upsert — updates if exists, inserts if not
        # Split chunks into individual documents with unique IDs
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        chunk_metadatas = [{**metadata, "chunk_index": i} for i in range(len(chunks))]

        # Delete old chunks first
        VectorService.delete_worker(worker_id)

        # Insert new chunks
        collection.add(
            ids=chunk_ids,
            documents=chunks,
            metadatas=chunk_metadatas
        )

    @staticmethod
    def query_worker(worker_id: str, question: str, n_results: int = 5) -> list[str]:
        collection = get_collection()
        doc_id = VectorService.get_doc_id(worker_id)

        try:
            results = collection.query(
                query_texts=[question],
                n_results=n_results,
                where={"worker_id": worker_id}
            )
            return results["documents"][0] if results["documents"] else []
        except Exception:
            return []

    @staticmethod
    def delete_worker(worker_id: str):
        collection = get_collection()
        try:
            # Get all chunk IDs for this worker
            results = collection.get(where={"worker_id": worker_id})
            if results["ids"]:
                collection.delete(ids=results["ids"])
        except Exception:
            pass

    @staticmethod
    def mark_dirty(worker_id: str, db):
        from database import execute_query
        from datetime import datetime
        execute_query(
            db,
            "UPDATE worker_rag_index SET is_dirty = true, updated_at = %s WHERE worker_id = %s",
            (datetime.utcnow(), worker_id)
        )
    @staticmethod
    def cleanup_after_post_completion(worker_ids: list[str], db):
        # Called when a post is marked completed
        # Check if worker is still active on other open posts
        # Only delete from vector DB if worker has no other open post engagements
        from database import execute_query
        for worker_id in worker_ids:
            active_posts = execute_query(
                db,
                """SELECT COUNT(*) as count FROM applications a
                   JOIN posts p ON p.id = a.post_id
                   WHERE a.worker_id = %s AND p.status = 'open' AND a.status = 'selected'""",
                (worker_id,),
                fetch="one"
            )
            if not active_posts or active_posts["count"] == 0:
                VectorService.delete_worker(worker_id)
                execute_query(
                    db,
                    "UPDATE worker_rag_index SET is_dirty = true WHERE worker_id = %s",
                    (worker_id,)
                )