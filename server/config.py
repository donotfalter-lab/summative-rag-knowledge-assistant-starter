import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    GENERATION_MODEL = os.getenv("GENERATION_MODEL", "llama3.2")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_assistant")
    KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base")

    TOP_K = int(os.getenv("TOP_K", "3"))
    MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.5"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

    CLIENT_ORIGIN = os.getenv("CLIENT_ORIGIN", "http://localhost:5173")
