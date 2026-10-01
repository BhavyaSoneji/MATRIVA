"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { FoodGuide } from "@/lib/care-types";
import { Chip, Frame } from "@/components/care/frame";

/**
 * What to eat: the book's regimen for the month of pregnancy (traditional, with the authority and scanned page), and the
 * foods that give most of a chosen nutrient (USDA values per everyday serving). Foods only: medicines are never advised.
 */
export function FoodsWidget() {
  const [guide, setGuide] = React.useState<FoodGuide | null>(null);
  const [need, setNeed] = React.useState<string | null>(null);
  const [month, setMonth] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const q = new URLSearchParams();
    if (need) q.set("need", need);
    if (month) q.set("month", String(month));
    api
      .get<FoodGuide>(`/care/food-guide${q.size ? `?${q}` : ""}`)
      .then((g) => {
        setGuide(g);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load the food guide."));
  }, [need, month]);

  if (error) return <Frame title="What to eat"><p className="text-sm text-blush-500">{error}</p></Frame>;
  if (!guide) return <Frame title="What to eat"><p className="text-sm text-muted-foreground">Loading…</p></Frame>;

  const t = guide.traditional;
  const shownMonth = guide.month;
  return (
    <Frame
      title="What to eat"
      note={`Foods only. For ${shownMonth ? `month ${shownMonth} of pregnancy` : "the month you choose"}${guide.diet ? `, ${guide.diet.replace(/_/g, " ")} diet` : ""}.`}
    >
      <div className="flex flex-wrap gap-2" role="group" aria-label="Month of pregnancy">
        {t.months_available.map((m) => (
          <Chip key={m} active={shownMonth === m} onClick={() => setMonth(m)}>
            Month {m}
          </Chip>
        ))}
      </div>

      {shownMonth && (
        <section className="mt-5 border-t border-border pt-4" aria-labelledby="trad-heading">
          <p id="trad-heading" className="eyebrow-sm text-accent">
            From the book · traditional (Ayurveda)
          </p>
          <p className="mt-1 text-[12px] text-muted-foreground">
            {t.book.title}, {t.book.author}, scanned pages {t.book.scan_pages}. This is classical knowledge, not modern clinical evidence.
          </p>
          <ul className="mt-3 flex flex-col gap-3">
            {t.foods.map((f, i) => (
              <li key={i} className="border-l-2 border-accent/40 pl-3 text-[14px] leading-relaxed">
                {f.text}
                <span className="block text-[11.5px] text-muted-foreground">
                  {f.authority} · scanned p. {f.page}
                  {f.paraphrased ? " · wording restated from a damaged scan" : ""}
                </span>
              </li>
            ))}
          </ul>
          {(t.skipped_for_diet ?? 0) > 0 && (
            <p className="mt-2 text-[12px] text-muted-foreground">
              {t.skipped_for_diet} more entr{t.skipped_for_diet === 1 ? "y" : "ies"} for this month use ingredients outside your diet and are not shown.
            </p>
          )}
          {(t.medicated.length > 0 || t.procedures.length > 0) && (
            <details className="mt-3 border border-border p-3 text-[13px]">
              <summary className="cursor-pointer text-muted-foreground">Treatments the book also describes (not food, not advice)</summary>
              <p className="mt-2 text-[12px] text-muted-foreground">{t.medicated_note}</p>
              <ul className="mt-2 flex flex-col gap-2">
                {[...t.medicated, ...t.procedures].map((f, i) => (
                  <li key={i} className="leading-relaxed">
                    {f.text}
                    <span className="block text-[11.5px] text-muted-foreground">{f.authority} · scanned p. {f.page}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {t.rationale && (
            <details className="mt-3 text-[13px]">
              <summary className="cursor-pointer text-muted-foreground">Why the book gives it this way (the book&apos;s own reasoning)</summary>
              <ul className="mt-2 list-disc pl-5 leading-relaxed">
                {t.rationale.points.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

      <section className="mt-6 border-t border-border pt-4" aria-labelledby="modern-heading">
        <p id="modern-heading" className="eyebrow-sm text-accent">
          Foods rich in a nutrient · modern
        </p>
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Nutrient">
          {guide.modern.needs.map((n) => (
            <Chip key={n.id} active={need === n.id} onClick={() => setNeed(need === n.id ? null : n.id)}>
              {n.label}
            </Chip>
          ))}
        </div>
        {guide.modern.need && (
          <div className="mt-4">
            <p className="text-[13px] text-muted-foreground">
              {guide.modern.need.label}: {guide.modern.need.reason}
              {guide.modern.need.daily_allowance ? ` · pregnancy allowance ${guide.modern.need.daily_allowance} ${guide.modern.need.unit} a day` : ""}
            </p>
            {guide.modern.foods.length === 0 ? (
              <p className="mt-2 text-sm">{guide.modern.empty_note}</p>
            ) : (
              <ul className="mt-3 flex flex-col">
                {guide.modern.foods.map((f) => (
                  <li key={f.name} className="flex items-baseline justify-between gap-3 border-t border-border py-2 text-[13.5px]">
                    <span>
                      {f.name}
                      <span className="text-muted-foreground"> · {f.serving_g} g</span>
                    </span>
                    <span className="shrink-0 font-semibold">
                      {f.amount} {guide.modern.need?.unit}
                      {f.percent !== null ? <span className="font-normal text-muted-foreground"> ({f.percent}%)</span> : null}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {guide.modern.need.tip && <p className="mt-3 text-[13px] leading-relaxed">{guide.modern.need.tip}</p>}
            {guide.modern.sources && (
              <p className="mt-2 text-[11.5px] text-muted-foreground">
                Values: {guide.modern.sources.map((s, i) => (
                  <React.Fragment key={s.url}>
                    {i > 0 && "; "}
                    <a href={s.url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-accent">{s.name}</a>
                  </React.Fragment>
                ))}
                . Approximate.
              </p>
            )}
          </div>
        )}
      </section>

      <details className="mt-6 border-t border-border pt-4 text-[13px]">
        <summary className="cursor-pointer text-muted-foreground">Foods to avoid or limit in pregnancy</summary>
        <ul className="mt-3 flex flex-col gap-2.5">
          {guide.avoid_modern.map((a) => (
            <li key={a.name} className="leading-relaxed">
              <span className="font-semibold">{a.name}</span>: {a.why}
            </li>
          ))}
        </ul>
        {t.avoid && (
          <>
            <p className="eyebrow-sm mt-4 text-muted-foreground">What the book lists as unsuitable (traditional)</p>
            <ul className="mt-2 flex flex-col gap-2.5">
              {t.avoid.items.map((a) => (
                <li key={a.authority} className="leading-relaxed">
                  {a.text} <span className="text-[11.5px] text-muted-foreground">{a.authority} · scanned p. {a.page}</span>
                  {a.modern && <span className="block text-[12px] text-muted-foreground">Modern guidance: {a.modern}</span>}
                </li>
              ))}
            </ul>
          </>
        )}
      </details>

      <ul className="mt-5 flex flex-col gap-1 text-[11.5px] text-muted-foreground">
        {guide.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </Frame>
  );
}
