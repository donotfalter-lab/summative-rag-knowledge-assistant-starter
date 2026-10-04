import { useEffect, useState } from "react";

const SAMPLE_QUESTIONS = [
  "What should I do if I cannot log into the product dashboard?",
  "Why are source-backed answers important?",
  "What should employees do with suspicious emails?",
  "What should a support agent do if the knowledge base does not answer a question?",
  "What should a new employee complete during the first week?"
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [status, setStatus] = useState("Checking backend...");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch("/api/health");
        const data = await response.json();

        if (response.ok) {
          setStatus(data.message || "Backend is running.");
        } else {
          setStatus("Backend responded, but not with a healthy status.");
        }
      } catch {
        setStatus("Backend is not reachable. Start Flask on port 5555.");
      }
    }

    checkBackend();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion) {
      setError("Enter a question before submitting.");
      return;
    }

    setIsLoading(true);
    setError("");
    setAnswer("");
    setSources([]);

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ question: trimmedQuestion })
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "The backend returned an error.");
      }

      setAnswer(data.answer || "");
      setSources(Array.isArray(data.sources) ? data.sources : []);
    } catch {
      setError("Could not reach the backend. Confirm Flask is running on port 5555.");
    } finally {
      setIsLoading(false);
    }
  }

  function useSampleQuestion(sample) {
    setQuestion(sample);
    setError("");
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Internal Knowledge Assistant</p>
        <h1>Local RAG-Powered Knowledge Assistant</h1>
        <p>
          Ask questions about onboarding, product support, security, and workplace
          processes. Answers are generated from the approved knowledge base and
          include the sources they came from.
        </p>
        <div className="status-card">
          <span className="status-dot" />
          <span>{status}</span>
        </div>
      </section>

      <section className="assistant-card">
        <form onSubmit={handleSubmit}>
          <label htmlFor="question">Ask a question about the knowledge base</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Example: Why are source-backed answers important?"
            rows={4}
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? "Working..." : "Ask Assistant"}
          </button>
        </form>

        <div className="sample-section">
          <p>Sample questions:</p>
          <div className="sample-list">
            {SAMPLE_QUESTIONS.map((sample) => (
              <button
                key={sample}
                type="button"
                className="sample-button"
                onClick={() => useSampleQuestion(sample)}
              >
                {sample}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="error-message">{error}</p>}

        {answer && (
          <section className="response-section">
            <h2>Answer</h2>
            <p className="answer-text">{answer}</p>
          </section>
        )}

        {sources.length > 0 && (
          <section className="sources-section">
            <h2>Sources</h2>
            <div className="source-list">
              {sources.map((source, index) => (
                <article className="source-card" key={`${source.source}-${index}`}>
                  <h3>{source.title || "Unknown Source"}</h3>
                  <p className="source-file">
                    {source.source}
                    {source.chunk_index !== undefined && source.chunk_index !== null &&
                      ` · chunk ${source.chunk_index}`}
                  </p>
                  <p>{source.excerpt}</p>
                </article>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
