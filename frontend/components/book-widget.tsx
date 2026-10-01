"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { BookChapter, BookOutline, GlossaryEntry } from "@/lib/types";
import { ChevronDown } from "lucide-react";

const STATUS: Record<string, { label: string; cls: string }> = {
  approved: { label: "Approved for answers", cls: "border-accent/50 text-accent" },
  pending: { label: "Awaiting review", cls: "border-border text-muted-foreground" },
  rejected: { label: "Rejected", cls: "border-blush-500/50 text-blush-500" },
};

function AuthorityBars({ authorities }: { authorities: Record<string, number> }) {
  const rows = Object.entries(authorities).slice(0, 7);
  const max = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <div className="flex flex-col gap-1.5">
      {rows.map(([name, n]) => (
        <div key={name} className="flex items-center gap-2 text-[11.5px]">
          <span className="w-24 shrink-0 text-muted-foreground">{name}</span>
          <div className="h-[3px] flex-1 bg-sage-100" role="img" aria-label={`${name} cited ${n} times`}>
            <div className="h-full bg-accent" style={{ width: `${(n / max) * 100}%` }} />
          </div>
          <span className="tabular w-8 shrink-0 text-right text-foreground">{n}</span>
        </div>
      ))}
    </div>
  );
}

function ChapterRow({ ch, status, onAsk }: { ch: BookChapter; status?: string; onAsk?: (q: string) => void }) {
  const st = STATUS[status ?? ""];
  return (
    <details className="group border-t border-border">
      <summary className="flex cursor-pointer list-none items-start gap-3 py-3">
        <span className="display w-7 shrink-0 text-xl text-accent">{ch.number}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-[14px] font-medium leading-snug">{ch.title_en}</span>
          {ch.title_hi && <span className="block text-[12px] text-muted-foreground">{ch.title_hi}</span>}
          <span className="mt-1 block text-[11px] text-muted-foreground">
            scanned pp. {ch.scan_start}–{ch.scan_end} · {ch.sections.length} sections · {ch.english_chunks} English passages
          </span>
        </span>
        {st && <span className={`hidden shrink-0 border px-2 py-0.5 text-[10.5px] sm:inline ${st.cls}`}>{st.label}</span>}
        <ChevronDown className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="grid gap-5 pb-4 pl-10 sm:grid-cols-2">
        <div>
          <p className="eyebrow-sm mb-2 text-muted-foreground">Sections — tap to ask</p>
          <ul className="flex flex-col gap-1">
            {ch.sections.map((s) => (
              <li key={`${s.scan_page}-${s.title_en}`}>
                <button
                  type="button"
                  onClick={() => onAsk?.(`What does the Prasuti Tantra say about ${s.title_en}?`)}
                  className="text-left text-[12.5px] leading-snug text-foreground underline decoration-border underline-offset-2 hover:text-accent"
                >
                  {s.title_en}
                </button>
                <span className="text-[11px] text-muted-foreground"> · p. {s.scan_page}</span>
              </li>
            ))}
            {ch.sections.length === 0 && <li className="text-[12px] text-muted-foreground">No sections could be verified for this chapter.</li>}
          </ul>
        </div>
        <div className="flex flex-col gap-4">
          {ch.concepts.length > 0 && (
            <div>
              <p className="eyebrow-sm mb-2 text-muted-foreground">Main concepts</p>
              <div className="flex flex-wrap gap-1.5">
                {ch.concepts.slice(0, 6).map((c) => (
                  <span key={c.id} className="border border-accent/40 px-2 py-0.5 text-[11px] text-accent">
                    {c.label} <span className="text-muted-foreground">{c.count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
          {ch.key_terms.length > 0 && (
            <div>
              <p className="eyebrow-sm mb-2 text-muted-foreground">Distinctive terms</p>
              <p className="text-[12px] italic text-foreground/80">{ch.key_terms.join(" · ")}</p>
            </div>
          )}
          {Object.keys(ch.authorities).length > 0 && (
            <p className="text-[11.5px] text-muted-foreground">
              Cites {Object.entries(ch.authorities).slice(0, 4).map(([n, c]) => `${n} (${c})`).join(", ")}
            </p>
          )}
        </div>
      </div>
    </details>
  );
}

function GlossarySearch({ onAsk }: { onAsk?: (q: string) => void }) {
  const [q, setQ] = React.useState("");
  const [results, setResults] = React.useState<GlossaryEntry[]>([]);
  React.useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    const id = setTimeout(() => {
      api
        .get<{ results: GlossaryEntry[] }>(`/knowledge/book/glossary?q=${encodeURIComponent(q.trim())}`)
        .then((r) => !cancelled && setResults(r.results))
        .catch(() => !cancelled && setResults([]));
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [q]);

  return (
    <div className="border-t border-border pt-4">
      <label htmlFor="glossary-q" className="eyebrow-sm text-muted-foreground">
        Hindi ↔ English glossary from the book
      </label>
      <input
        id="glossary-q"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search a term, e.g. stanya, दौहद, abortion"
        className="mt-2 h-10 w-full border border-border bg-transparent px-3 text-sm outline-none placeholder:text-muted-foreground/70 focus:border-accent"
      />
      {results.length > 0 && (
        <ul className="mt-2 flex flex-col">
          {results.map((r) => (
            <li key={`${r.hi}-${r.en}`} className="flex items-baseline gap-3 border-b border-border py-1.5 text-[12.5px]">
              <span className="w-1/2 shrink-0">{r.hi}</span>
              <button type="button" className="text-left text-foreground hover:text-accent" onClick={() => onAsk?.(`What is ${r.en}?`)}>
                {r.en}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The book as a structure: chapters, sections, concepts, authorities, glossary -- recovered from the OCR. */
export function BookWidget({ onAsk }: { onAsk?: (question: string) => void }) {
  const [book, setBook] = React.useState<BookOutline | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    api
      .get<BookOutline>("/knowledge/book")
      .then((b) => !cancelled && setBook(b))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : "Could not load the book."));
    return () => {
      cancelled = true;
    };
  }, []);

  const frame = (children: React.ReactNode) => (
    <section className="border border-border bg-card p-5">
      <h3 className="eyebrow mb-4 text-accent">The book</h3>
      {children}
    </section>
  );
  if (error) return frame(<p className="text-sm text-blush-500">{error}</p>);
  if (!book) return frame(<p className="text-sm text-muted-foreground">Opening the book…</p>);
  if (!book.available) return frame(<p className="text-sm text-muted-foreground">The book index has not been built yet.</p>);

  return frame(
    <div className="flex flex-col gap-5">
      <div>
        <p className="display text-[1.35rem] leading-[1.15]">{book.title}</p>
        <p className="mt-1 text-[12.5px] text-muted-foreground">
          {book.author} · {book.publisher}
        </p>
        <p className="mt-2 text-[11.5px] text-muted-foreground">
          {book.chapters.length} chapters · {book.stats.verified_sections} verified sections · {book.stats.english_chunks} English passages ·{" "}
          {book.stats.scanned_pages} scanned pages. Recovered from an OCR scan; not clinically reviewed.
        </p>
      </div>
      <div>
        <p className="eyebrow-sm mb-2 text-muted-foreground">Classical authorities cited</p>
        <AuthorityBars authorities={book.authorities} />
      </div>
      <div>
        {book.chapters.map((ch) => (
          <ChapterRow key={ch.number} ch={ch} status={book.review?.[String(ch.number)]} onAsk={onAsk} />
        ))}
      </div>
      <GlossarySearch onAsk={onAsk} />
    </div>
  );
}
