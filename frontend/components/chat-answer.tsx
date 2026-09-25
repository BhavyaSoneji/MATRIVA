import type { SourceResponse } from "@/lib/types";
import { EvidenceBadge } from "@/components/evidence-badge";

/**
 * Renders an assistant answer. The backend's local (no-LLM-key) fallback
 * composes answers as literal bullet lines ending in `[source_id=<id>]`
 * (see backend `app/llm/generator.py::_local_grounded_answer`) — that reads
 * as a raw data dump if printed verbatim, so any line matching that shape is
 * rendered as a proper evidence row instead. Prose paragraphs (the shape a
 * live LLM provider returns) pass through unchanged. Both forms can appear
 * in the same answer, so this checks per line rather than per whole answer.
 */
const BULLET_RE = /^-\s+(.*?)\s*\[source_id=([a-zA-Z0-9]+)\]\s*$/;

export function ChatAnswer({ text, sources }: { text: string; sources: SourceResponse[] }) {
  const byId = new Map(sources.map((s) => [s.id, s]));
  const paragraphs = text.split(/\n{2,}/);

  return (
    <div className="flex flex-col gap-4">
      {paragraphs.map((para, i) => {
        const lines = para.split("\n").filter((l) => l.trim().length > 0);
        const matches = lines.map((l) => l.match(BULLET_RE));

        if (lines.length > 0 && matches.every(Boolean)) {
          return (
            <ul key={i} className="flex flex-col gap-3">
              {matches.map((m, j) => {
                const [, body, sourceId] = m!;
                const source = byId.get(sourceId);
                const [name, ...rest] = body.split(":");
                const snippet = rest.length > 0 ? rest.join(":").trim() : body;
                return (
                  <li key={j} className="border-l-2 border-accent/40 pl-3.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                      <span className="text-[13px] font-bold text-foreground">
                        {source?.title || name.trim()}
                      </span>
                      {source && <EvidenceBadge level={source.evidence_level} />}
                    </div>
                    <p className="mt-1 text-[15px] leading-[1.65] text-muted-foreground">
                      {rest.length > 0 ? snippet : ""}
                    </p>
                  </li>
                );
              })}
            </ul>
          );
        }

        return (
          <p key={i} className="whitespace-pre-wrap text-[16px] leading-[1.65]">
            {para}
          </p>
        );
      })}
    </div>
  );
}
