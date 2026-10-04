import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config
from rag_service import answer_question

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": Config.CLIENT_ORIGIN}})


@app.get("/api/health")
def health():
    """Confirm that the backend is running."""
    return jsonify(
        {
            "status": "ok",
            "message": "Backend is running.",
        }
    ), 200


@app.post("/api/ask")
def ask_question():
    """
    Receive a question from the frontend and return an answer with sources.

    Steps:
    - Read JSON from the request body.
    - Validate that the question exists and is not blank.
    - Call answer_question(question).
    - Return the result as JSON.
    - Return a helpful error response if the question is missing.
    """
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")
    question = question.strip() if isinstance(question, str) else ""

    if not question:
        return jsonify({"error": "Question is required."}), 400

    try:
        result = answer_question(question)
    except requests.exceptions.RequestException:
        app.logger.exception("Model service request failed.")
        return jsonify(
            {
                "error": (
                    "Could not reach the model service. Confirm Ollama is running "
                    f"at {Config.OLLAMA_BASE_URL} and the configured models are pulled."
                ),
                "sources": [],
            }
        ), 503
    except Exception:
        app.logger.exception("RAG workflow failed.")
        return jsonify(
            {
                "error": "Something went wrong while generating an answer.",
                "sources": [],
            }
        ), 500

    return jsonify(result), 200


if __name__ == "__main__":
    app.run(debug=True, port=5555)
