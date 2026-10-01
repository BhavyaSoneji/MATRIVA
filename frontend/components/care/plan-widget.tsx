"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { CarePlan, Reminder } from "@/lib/care-types";
import { WeekRing } from "@/components/week-ring";
import { Frame } from "@/components/care/frame";
import { Bell, CalendarCheck, Pill, BookOpen } from "lucide-react";

export type CareAction = "checkin" | "summary" | "readings" | "screen" | "meals" | "foods" | "plan";

function fmt(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** "My plan": where you are, what is due, the visit calendar, what to take, and what to read this week. */
export function PlanWidget({ onAsk, onOpen }: { onAsk?: (q: string) => void; onOpen?: (a: CareAction) => void }) {
  const [plan, setPlan] = React.useState<CarePlan | null>(null);
  const [reminders, setReminders] = React.useState<Reminder[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api.get<CarePlan>("/care/plan").then(setPlan).catch((e) => setError(e instanceof ApiError ? e.message : "Could not load your plan."));
    api.get<{ reminders: Reminder[] }>("/care/reminders").then((r) => setReminders(r.reminders)).catch(() => undefined);
  }, []);

  if (error) {
    return (
      <Frame title="My plan">
        <p className="text-sm text-muted-foreground">{error} Add your last period date or due date in Settings to unlock your weekly plan.</p>
      </Frame>
    );
  }
  if (!plan) return <Frame title="My plan"><p className="text-sm text-muted-foreground">Loading your plan…</p></Frame>;

  return (
    <Frame title="My plan">
      <div className="flex flex-wrap items-center gap-6">
        <WeekRing week={plan.week} size={118} stroke={2.5} />
        <div className="min-w-[200px] flex-1">
          <p className="display text-2xl leading-tight">{plan.headline}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Due {fmt(plan.edd)} · {Math.max(plan.days_to_edd, 0)} days to go
            {plan.source_of_dates === "week" ? " · estimated from the week you gave" : ""}
          </p>
          <div className="mt-3 h-[3px] w-full bg-sage-100" role="img" aria-label={`${Math.round(plan.progress * 100)}% of the way`}>
            <div className="h-full bg-accent" style={{ width: `${plan.progress * 100}%` }} />
          </div>
        </div>
      </div>

      {reminders.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <p className="eyebrow-sm mb-2 flex items-center gap-1.5 text-accent"><Bell className="h-3 w-3" aria-hidden="true" /> Needs attention</p>
          <ul className="flex flex-col gap-2">
            {reminders.map((r) => (
              <li key={r.id} className="flex items-start justify-between gap-3 border border-border p-3">
                <span>
                  <span className="block text-[13.5px] font-medium">{r.title}</span>
                  <span className="block text-[12px] leading-snug text-muted-foreground">{r.detail}</span>
                </span>
                {r.action && (
                  <button type="button" onClick={() => onOpen?.(r.action as CareAction)} className="eyebrow-sm h-9 shrink-0 border border-border px-3 hover:border-accent hover:text-accent">
                    Open
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 grid gap-5 border-t border-border pt-4 sm:grid-cols-2">
        <div>
          <p className="eyebrow-sm mb-2 flex items-center gap-1.5 text-muted-foreground"><CalendarCheck className="h-3 w-3" aria-hidden="true" /> Visit calendar</p>
          <ul className="flex flex-col gap-1">
            {plan.visits.map((v) => (
              <li key={v.week} className={`flex items-baseline justify-between text-[12.5px] ${v.status === "past" ? "text-muted-foreground/60 line-through" : v.status === "due_now" ? "font-semibold text-accent" : ""}`}>
                <span>Week {v.week}</span>
                <span>{fmt(v.date)}{v.status === "due_now" ? " · now" : ""}</span>
              </li>
            ))}
          </ul>
          {plan.pmsma && (
            <p className="mt-3 text-[12px] text-muted-foreground">
              Free PMSMA check-up: <span className="text-foreground">{fmt(plan.pmsma.date)}</span> ({plan.pmsma.days_away} days).{" "}
              <a href={plan.pmsma.url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-accent">About PMSMA</a>
            </p>
          )}
        </div>
        <div>
          <p className="eyebrow-sm mb-2 flex items-center gap-1.5 text-muted-foreground"><Pill className="h-3 w-3" aria-hidden="true" /> Supplements</p>
          <ul className="flex flex-col gap-2.5">
            {plan.supplements.map((s) => (
              <li key={s.id} className={s.active ? "" : "opacity-50"}>
                <span className="block text-[13px] font-medium">{s.label} {s.active ? <span className="text-accent">· now</span> : null}</span>
                <span className="block text-[12px] leading-snug text-muted-foreground">
                  {s.instruction} <a href={s.url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-accent">{s.source}</a>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-5 border-t border-border pt-4">
        <p className="eyebrow-sm mb-2 flex items-center gap-1.5 text-muted-foreground"><BookOpen className="h-3 w-3" aria-hidden="true" /> This week — tap to learn more</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {plan.this_week.filter((t) => t.kind !== "supplement").map((t) => (
            <button key={t.id} type="button" onClick={() => t.ask && onAsk?.(t.ask)} className="lift border border-border p-3 text-left">
              <span className="block text-[13.5px] font-medium">{t.title}</span>
              <span className="mt-1 block text-[12px] leading-snug text-muted-foreground">{t.detail}</span>
              <span className="mt-1.5 block text-[10.5px] text-muted-foreground/70">{t.source}</span>
            </button>
          ))}
        </div>
      </div>
      <p className="mt-4 text-[11px] text-muted-foreground">Schedules follow the sources shown and have not yet been signed off by a clinician. Your own doctor&apos;s plan always comes first.</p>
    </Frame>
  );
}
