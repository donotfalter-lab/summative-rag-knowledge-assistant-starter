from typing import Any, List

import chromadb
import requests
from chromadb.config import Settings

from config import Config
from documents import DocumentChunk


def get_chroma_client():
    """
    Create and return a persistent Chroma client.

    Steps:
    - Use Config.CHROMA_PATH as the local storage path.
    - Return a chromadb.PersistentClient.
    """
    return chromadb.PersistentClient(
        path=Config.CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )


def get_or_create_collection():
    """
    Get or create the Chroma collection for the knowledge assistant.

    Steps:
    - Use get_chroma_client().
    - Use Config.COLLECTION_NAME as the collection name.
    - Return the collection.
    """
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=Config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def get_embedding(text: str) -> list[float]:
    """
    Create an embedding for a piece of text using the local model service.

    Steps:
    - Send a POST request to the Ollama embed endpoint (https://docs.ollama.com/api/embed).
    - Use Config.OLLAMA_BASE_URL.
    - Use Config.EMBEDDING_MODEL.
    - Return the embedding list from the response.

    Endpoint:
        POST {OLLAMA_BASE_URL}/api/embed

    Example request body:
        {
            "model": Config.EMBEDDING_MODEL,
            "input": text
        }
    """
    response = requests.post(
        f"{Config.OLLAMA_BASE_URL}/api/embed",
        json={"model": Config.EMBEDDING_MODEL, "input": text},
        timeout=60,
    )
    response.raise_for_status()

    embeddings = response.json().get("embeddings") or []
    if not embeddings:
        raise ValueError("The embedding model returned no embeddings.")

    return embeddings[0]


def seed_vector_store(chunks: List[DocumentChunk]) -> int:
    """
    Add document chunks to the Chroma collection.

    Steps:
    - Get or create the collection.
    - Convert each chunk into:
        - id
        - document text
        - metadata with source, title, and chunk_index
        - embedding
    - Add or update the chunks in Chroma (recommend using collection.upsert(...) to prevent duplicating existing records).
    - Return the number of chunks added.

    Keep source metadata because the frontend needs to display sources.
    """
    if not chunks:
        return 0

    collection = get_or_create_collection()

    collection.upsert(
        ids=[chunk.id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        metadatas=[
            {
                "source": chunk.source,
                "title": chunk.title,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ],
        embeddings=[get_embedding(chunk.text) for chunk in chunks],
    )

    return len(chunks)


def retrieve_relevant_chunks(question: str, top_k: int | None = None) -> list[dict[str, Any]]:
    """
    Retrieve relevant chunks for a user question.

    Steps:
    - Create an embedding for the question.
    - Query the Chroma collection.
    - Return a list of dictionaries with:
        - text
        - source
        - title
        - chunk_index
        - distance (cosine distance; lower is more relevant)

    Chunks farther than Config.MAX_DISTANCE from the question are dropped.

    The RAG workflow expects a list shaped like this:

        [
            {
                "text": "Relevant source text...",
                "source": "product_support.txt",
                "title": "Product Support Guide",
                "chunk_index": 0
            }
        ]
    """
    collection = get_or_create_collection()

    if collection.count() == 0:
        return []

    n_results = min(top_k or Config.TOP_K, collection.count())

    results = collection.query(
        query_embeddings=[get_embedding(question)],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    chunks = []

    for text, metadata, distance in zip(documents, metadatas, distances):
        # Skip chunks that are too far from the question to be useful context.
        if distance > Config.MAX_DISTANCE:
            continue

        metadata = metadata or {}
        chunks.append(
            {
                "text": text,
                "source": metadata.get("source", "unknown"),
                "title": metadata.get("title", "Unknown Source"),
                "chunk_index": metadata.get("chunk_index"),
                "distance": distance,
            }
        )

    return chunks
