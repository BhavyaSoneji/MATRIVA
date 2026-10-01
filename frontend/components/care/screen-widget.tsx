"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { ScreeningQuestion, Triage } from "@/lib/care-types";
import { Button } from "@/components/ui/button";
import { TriageResult } from "@/components/care/triage";

/** A short yes/no red-flag check (/check). Every question names the guidance it comes from. */
export function ScreenWidget() {
  const [questions, setQuestions] = React.useState<ScreeningQuestion[]>([]);
  const [week, setWeek] = React.useState<number | null>(null);
  const [answers, setAnswers] = React.useState<Record<string, boolean>>({});
  const [result, setResult] = React.useState<Triage | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .get<{ week: number | null; questions: ScreeningQuestion[] }>("/care/screening/questions")
      .then((r) => {
        setQuestions(r.questions);
        setWeek(r.week);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load the questions."));
  }, []);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.post<Triage>("/care/screening/assess", { answers }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not check your answers.");
    } finally {
      setBusy(false);
    }
  };

  const yes = Object.values(answers).filter(Boolean).length;
  return (
    <section className="border border-border bg-card p-5">
      <h3 className="eyebrow mb-1 text-accent">Quick safety check</h3>
      <p className="mb-4 text-[12.5px] text-muted-foreground">
        Tick anything that is true right now{week ? ` (week ${week})` : ""}. This is a checklist, not a diagnosis. In an emergency call 112 first.
      </p>
      {error && <p className="mb-3 text-sm text-blush-500">{error}</p>}
      {result ? (
        <div className="flex flex-col gap-4">
          <TriageResult result={result} />
          <button type="button" onClick={() => setResult(null)} className="eyebrow-sm w-fit text-muted-foreground hover:text-accent">
            ← Change my answers
          </button>
        </div>
      ) : (
        <>
          <ul className="flex flex-col">
            {questions.map((q) => (
              <li key={q.id} className="border-t border-border">
                <label className="flex min-h-12 cursor-pointer items-start gap-3 py-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 shrink-0 accent-[hsl(var(--accent))]"
                    checked={!!answers[q.id]}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.checked }))}
                  />
                  <span className="text-[14px] leading-snug">
                    {q.text}
                    <a href={q.url} target="_blank" rel="noreferrer" className="ml-2 text-[11px] text-muted-foreground underline underline-offset-2 hover:text-accent">
                      {q.source}
                    </a>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex items-center gap-4">
            <Button onClick={submit} disabled={busy || questions.length === 0}>
              {busy ? "Checking…" : yes > 0 ? `Check my ${yes} answer${yes === 1 ? "" : "s"}` : "Nothing applies"}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
