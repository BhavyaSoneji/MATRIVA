import * as React from "react";
import type { SourceResponse } from "@/lib/types";
import { EvidenceBadge } from "@/components/evidence-badge";

/**
 * Renders an assistant answer.
 *
 * Understands the small markup the local RAG engine (and the LLM prompt) produce, and nothing more:
 *   **HEADING**        a section heading (whole line)
 *   - sentence [1]     a bullet; [1], [2,3] become clickable citation chips
 *   > note             a personalised callout (stage, allergy, diet)
 *   _line_             a muted note (whole line)
 *   **bold** inline
 * Anything else is a plain paragraph. It never injects HTML -- everything is built as React nodes.
 *
 * The older "- Name: snippet [source_id=<id>]" lines (the no-LLM fallback of the external pipeline) are still
 * rendered as evidence rows.
 */
const LEGACY_BULLET_RE = /^-\s+(.*?)\s*\[source_id=([a-zA-Z0-9]+)\]\s*$/;
const INLINE_RE = /(\*\*[^*]+\*\*|\[\d+(?:\s*,\s*\d+)*\])/g;
const HEADING_RE = /^\*\*([^*]+)\*\*:?$/;
const NOTE_RE = /^_(.+)_$/;

function Inline({ text, citeId }: { text: string; citeId?: string }) {
  const parts = text.split(INLINE_RE).filter((p) => p !== "");
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="font-semibold text-foreground">
              {part.slice(2, -2)}
            </strong>
          );
        }
        const cite = part.match(/^\[(\d+(?:\s*,\s*\d+)*)\]$/);
        if (cite && citeId) {
          return (
            <span key={i} className="whitespace-nowrap">
              {cite[1].split(",").map((n) => (
                <a
                  key={n}
                  href={`#${citeId}-${n.trim()}`}
                  aria-label={`Source ${n.trim()}`}
                  className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center border border-accent/50 px-1 align-baseline text-[10.5px] font-semibold leading-none text-accent no-underline transition-colors hover:bg-accent hover:text-primary-foreground"
                >
                  {n.trim()}
                </a>
              ))}
            </span>
          );
        }
        return <React.Fragment key={i}>{part}</React.Fragment>;
      })}
    </>
  );
}

export function ChatAnswer({
  text,
  sources,
  citeId,
}: {
  text: string;
  sources: SourceResponse[];
  /** prefix for citation anchors, e.g. "cite-<messageId>"; the citation list uses `${citeId}-${n}` ids */
  citeId?: string;
}) {
  const byId = new Map(sources.map((s) => [s.id, s]));
  const blocks = text.split(/\n{2,}/);

  return (
    <div className="flex flex-col gap-3.5">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim().length > 0);
        if (lines.length === 0) return null;

        // legacy evidence rows
        const legacy = lines.map((l) => l.match(LEGACY_BULLET_RE));
        if (legacy.every(Boolean)) {
          return (
            <ul key={bi} className="flex flex-col gap-3">
              {legacy.map((m, j) => {
                const [, body, sourceId] = m!;
                const source = byId.get(sourceId);
                const [name, ...rest] = body.split(":");
                return (
                  <li key={j} className="border-l-2 border-accent/40 pl-3.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                      <span className="text-[13px] font-bold text-foreground">{source?.title || name.trim()}</span>
                      {source && <EvidenceBadge level={source.evidence_level} />}
                    </div>
                    <p className="mt-1 text-[15px] leading-[1.65] text-muted-foreground">
                      {rest.length > 0 ? rest.join(":").trim() : body}
                    </p>
                  </li>
                );
              })}
            </ul>
          );
        }

        const bullets: string[] = [];
        const out: React.ReactNode[] = [];
        const flushBullets = (key: string) => {
          if (bullets.length === 0) return;
          const items = bullets.splice(0);
          out.push(
            <ul key={key} className="flex flex-col gap-2.5">
              {items.map((b, k) => (
                <li key={k} className="relative pl-4 text-[15.5px] leading-[1.65] before:absolute before:left-0 before:top-[0.72em] before:h-1 before:w-1 before:bg-accent">
                  <Inline text={b} citeId={citeId} />
                </li>
              ))}
            </ul>
          );
        };

        lines.forEach((line, li) => {
          const t = line.trim();
          const key = `${bi}-${li}`;
          if (t.startsWith("- ") || t.startsWith("* ")) {
            bullets.push(t.slice(2));
            return;
          }
          flushBullets(`${key}-b`);
          const heading = t.match(HEADING_RE);
          const note = t.match(NOTE_RE);
          if (heading) {
            out.push(
              <p key={key} className="eyebrow mt-1 text-accent">
                {heading[1]}
              </p>
            );
          } else if (t.startsWith("> ")) {
            out.push(
              <p key={key} className="border-l-2 border-blush-500 bg-blush-100/60 px-3.5 py-2.5 text-[13.5px] leading-relaxed text-foreground/85">
                <Inline text={t.slice(2)} citeId={citeId} />
              </p>
            );
          } else if (note) {
            out.push(
              <p key={key} className="text-[12.5px] italic leading-relaxed text-muted-foreground">
                {note[1]}
              </p>
            );
          } else {
            out.push(
              <p key={key} className="whitespace-pre-wrap text-[16px] leading-[1.65]">
                <Inline text={t} citeId={citeId} />
              </p>
            );
          }
        });
        flushBullets(`${bi}-end`);
        return (
          <div key={bi} className="flex flex-col gap-2.5">
            {out}
          </div>
        );
      })}
    </div>
  );
}
