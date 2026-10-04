from config import Config
from documents import build_chunks, load_text_documents
from vector_store import seed_vector_store


def main():
    """
    Load the provided knowledge base and store document chunks in Chroma.

    Run this again whenever the knowledge base files change; upsert keeps it idempotent.
    """
    documents = load_text_documents(Config.KNOWLEDGE_BASE_PATH)
    chunks = build_chunks(documents)

    count = seed_vector_store(chunks)

    print(f"Loaded {len(documents)} documents.")
    print(f"Prepared {len(chunks)} chunks.")
    print(f"Stored {count} chunks in collection '{Config.COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
