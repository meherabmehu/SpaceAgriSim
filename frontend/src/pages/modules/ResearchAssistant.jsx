import { useEffect, useState } from "react";
import { Card } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import { useResource, RequestState, JsonDetails } from "./moduleSupport.jsx";
import {
  BookOpenCheck,
  ExternalLink,
  MessageSquare,
  Search,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

const MAX_QUESTION = 300;

// Status vocabulary returned by /assistant/ask. Only "grounded" means every sentence is
// backed by retrieved evidence; "partial" and "insufficient" must never look the same.
const STATUS_COPY = {
  grounded:
    "Every statement below is quoted from retrieved evidence, with the passage cited.",
  partial:
    "Only part of the question could be grounded. The cited passages do not cover all of it.",
  insufficient:
    "The repository evidence does not answer this question, so the assistant refused rather than invent an answer.",
};

function CitationList({ citations }) {
  if (!citations?.length) return null;
  return (
    <ol className="citation-list">
      {citations.map((citation, index) => (
        <li key={`${citation.sourceId}-${index}`}>
          <div className="citation-head">
            <strong>
              {index + 1}. {citation.title}
            </strong>
            <span className="pill">{citation.evidenceClass}</span>
          </div>
          <div className="citation-meta">
            {citation.accession ? <span>Accession {citation.accession}</span> : null}
            {citation.url ? (
              <a href={citation.url} target="_blank" rel="noreferrer noopener">
                {citation.accession ? "Source" : "Link"} <ExternalLink size={12} />
              </a>
            ) : null}
          </div>
          {citation.localReference && (
            <code className="citation-ref">{citation.localReference}</code>
          )}
          {citation.limitations?.length ? (
            <ul className="citation-limits">
              {citation.limitations.map((limitation, i) => (
                <li key={i}>{limitation}</li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

export function ResearchAssistant() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestionList, setSuggestionList] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    api("/assistant/suggestions", undefined, controller.signal)
      .then((data) => setSuggestionList(data?.suggestions || []))
      .catch(() => setSuggestionList([]));
    return () => controller.abort();
  }, []);

  const ask = async (text) => {
    const trimmed = (text ?? question).trim();
    if (!trimmed) {
      setError("Enter a question about the repository's evidence.");
      return;
    }
    if (trimmed.length > MAX_QUESTION) {
      setError(`Questions are limited to ${MAX_QUESTION} characters.`);
      return;
    }
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(await api("/assistant/ask", { question: trimmed }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const status = answer?.status;
  const refused = status === "insufficient" || Boolean(answer?.refusal);

  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <MessageSquare size={12} />
          EVIDENCE-GROUNDED RESEARCH ASSISTANT
        </span>
        <p>
          Answers are assembled from retrieved repository evidence and every claim
          carries a citation to a study accession, a local file, or a model
          registry entry. When the evidence does not cover a question, the
          assistant says so instead of answering. Measured data and model
          interpretation are labelled separately.
        </p>
      </div>

      <Card
        title="Ask the evidence"
        label="RETRIEVAL OVER 46 VERIFIED PASSAGES"
        action={<BookOpenCheck size={18} className="accent" />}
      >
        <div className="search-row">
          <Search size={16} className="muted" />
          <input
            type="search"
            aria-label="Ask a question about the repository evidence"
            placeholder="e.g. Is OSD-320 an independent replication of OSD-46?"
            value={question}
            maxLength={MAX_QUESTION}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") ask();
            }}
          />
        </div>
        <div className="module-actions">
          <button className="primary-button" disabled={busy} onClick={() => ask()}>
            {busy ? "Retrieving evidence…" : "Ask"}
          </button>
          <span className="muted fine">
            {question.length}/{MAX_QUESTION} characters
          </span>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        {suggestionList.length > 0 && (
          <div className="badge-row">
            {suggestionList.slice(0, 5).map((suggestion) => (
              <button
                key={suggestion.question}
                className="pill"
                type="button"
                title={`Answered from: ${suggestion.answeredBy}`}
                onClick={() => {
                  setQuestion(suggestion.question);
                  ask(suggestion.question);
                }}
              >
                {suggestion.question}
              </button>
            ))}
          </div>
        )}
      </Card>

      {answer && (
        <Card
          title="Answer"
          label={`GROUNDING · ${answer.status?.toUpperCase()}`}
          action={
            <span className={refused ? "pill amber" : "pill green"}>
              {refused ? <ShieldAlert size={12} /> : <ShieldCheck size={12} />}
              {refused ? "Refused" : "Cited"}
            </span>
          }
        >
          <p className="muted fine">{STATUS_COPY[status] || ""}</p>

          {refused ? (
            <div className="warning-box">
              <p>
                {answer.summary ||
                  "The repository evidence does not contain enough information to answer this question."}
              </p>
            </div>
          ) : (
            <>
              <p className="prose">{answer.summary}</p>
              <ul className="claim-list">
                {(answer.claims || []).map((claim, index) => (
                  <li key={index}>
                    <span>{claim.text}</span>
                    <span className="pill">[{claim.citation}]</span>
                  </li>
                ))}
              </ul>
              <h3 className="sub-heading">Citations</h3>
              <CitationList citations={answer.citations} />
            </>
          )}

          <h3 className="sub-heading">Measured data versus model interpretation</h3>
          <div className="stat-pair">
            <span>Measured data</span>
            <strong>
              {answer.measuredVersusInterpreted?.measuredData?.join(", ") || "none cited"}
            </strong>
          </div>
          <div className="stat-pair">
            <span>Model or estimate</span>
            <strong>
              {answer.measuredVersusInterpreted?.modelOrEstimate?.join(", ") ||
                "none cited"}
            </strong>
          </div>
          {answer.measuredVersusInterpreted?.note && (
            <p className="muted fine">{answer.measuredVersusInterpreted.note}</p>
          )}

          {answer.limitations?.length > 0 && (
            <div className="warning-box">
              {answer.limitations.map((limitation, index) => (
                <p key={index}>{limitation}</p>
              ))}
            </div>
          )}

          <JsonDetails
            title="Retrieval scores, intent and grounding detail"
            data={{
              intent: answer.intent,
              grounding: answer.grounding,
              claims: answer.claims,
              citations: answer.citations,
            }}
          />
        </Card>
      )}

      <Card
        title="What this assistant can and cannot see"
        label="CORPUS BOUNDARY"
        action={<BookOpenCheck size={18} className="muted" />}
      >
        <p className="prose">
          The corpus is built only from repository artifacts: the OSDR study
          manifest, the model registry, the Phase 9–11 evaluation records, and the
          methodology notes. Retrieved documents are screened before indexing and
          are never treated as instructions. If a passage was quarantined, it is
          unavailable to answers.
        </p>
        <CorpusStatus />
      </Card>
    </>
  );
}

function CorpusStatus() {
  const state = useResource("/assistant/corpus");
  return (
    <>
      <RequestState state={state} />
      {state.data && (
        <div className="badge-row">
          <span className="pill">{state.data.passages} passages</span>
          <span className="pill green">{state.data.quarantined} quarantined</span>
          {Object.entries(state.data.byKind || {}).map(([kind, count]) => (
            <span className="pill" key={kind}>
              {kind}: {count}
            </span>
          ))}
        </div>
      )}
    </>
  );
}
