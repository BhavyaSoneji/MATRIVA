import type { RetrievalTrace } from "@/lib/types";

function Bar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-2">
      <span className="w-[68px] shrink-0 text-[10.5px] text-muted-foreground">{label}</span>
      <div className="h-[3px] flex-1 bg-sage-100" role="img" aria-label={`${label} ${pct}%`}>
        <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular w-8 shrink-0 text-right text-[10.5px] text-foreground">{pct}%</span>
    </div>
  );
}

const CONFIDENCE_LABEL = (c: number) => (c >= 0.65 ? "Strong" : c >= 0.45 ? "Moderate" : "Partial");

/** Shows how the offline RAG engine found an answer: what it understood, what it searched, what it scored. */
export function RetrievalTracePanel({ trace }: { trace: RetrievalTrace }) {
  return (
    <div className="mt-3 flex flex-col gap-4 border-l-2 border-border pl-4 text-[11.5px] text-muted-foreground">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="eyebrow-sm">Match</p>
          <p className="mt-1 text-foreground">
            {CONFIDENCE_LABEL(trace.confidence)} · {Math.round(trace.confidence * 100)}%
          </p>
          <div className="mt-1.5 h-[3px] w-full bg-sage-100">
            <div className="h-full bg-accent" style={{ width: `${Math.round(trace.confidence * 100)}%` }} />
          </div>
          <p className="mt-1.5">Searched {trace.passages_searched.toLocaleString()} approved passages, offline.</p>
        </div>
        <div>
          <p className="eyebrow-sm">Understood as</p>
          {trace.concepts.length > 0 ? (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {trace.concepts.map((c) => (
                <span key={c} className="border border-accent/40 px-2 py-0.5 text-[11px] text-accent">
                  {c}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-foreground">{trace.query_terms.join(", ") || "—"}</p>
          )}
          {trace.related_concepts && trace.related_concepts.length > 0 && (
            <p className="mt-1.5">Also searched: {trace.related_concepts.join(", ")}</p>
          )}
        </div>
      </div>

      {trace.passages.length > 0 && (
        <ol className="flex flex-col gap-3">
          {trace.passages.slice(0, 5).map((p, i) => (
            <li key={i} className="flex flex-col gap-1.5 border-t border-border pt-3">
              <p className="text-foreground">
                {p.citation ? <span className="eyebrow-sm mr-2 text-accent">[{p.citation}]</span> : null}
                {p.title}
                {p.locator ? <span className="text-muted-foreground"> · {p.locator}</span> : null}
              </p>
              <div className="grid gap-x-6 gap-y-1 sm:grid-cols-3">
                <Bar value={p.bm25 / 0.6} label="Word match" />
                <Bar value={p.ngram} label="Spelling-tolerant" />
                <Bar value={p.coverage} label="Question covered" />
              </div>
              {p.matched_concepts.length > 0 && <p>Concepts: {p.matched_concepts.join(", ")}</p>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
