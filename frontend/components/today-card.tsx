"use client";

import * as React from "react";
import { api } from "@/lib/api";
import type { NextVisitResponse, PregnancyResponse, WellnessLog } from "@/lib/types";
import { CalendarHeart, Droplets } from "lucide-react";

const ML_PER_GLASS = 250;

/** The one-glance "today" strip shown above the first message: where you are, your next visit,
 * and a one-tap water log. Quietly renders nothing for a user with no pregnancy details yet. */
export function TodayCard({ pregnancy }: { pregnancy: PregnancyResponse | null }) {
  const [visit, setVisit] = React.useState<NextVisitResponse | null>(null);
  const [waterMl, setWaterMl] = React.useState(0);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    if (!pregnancy) return;
    let cancelled = false;
    api
      .get<NextVisitResponse>("/pregnancy/next-visit")
      .then((v) => !cancelled && setVisit(v))
      .catch(() => undefined);
    api
      .get<WellnessLog>("/wellness/daily")
      .then((l) => !cancelled && setWaterMl(l.water_intake_ml ?? 0))
      .catch(() => undefined); // 404 = nothing logged yet today
    return () => {
      cancelled = true;
    };
  }, [pregnancy]);

  if (!pregnancy) return null;

  const addGlass = async () => {
    const next = waterMl + ML_PER_GLASS;
    setSaving(true);
    try {
      await api.put("/wellness/daily", { water_intake_ml: next });
      setWaterMl(next);
    } catch {
      // leave the count unchanged if saving fails
    } finally {
      setSaving(false);
    }
  };

  return (
    <section aria-label="Today" className="mx-auto mb-8 grid w-full max-w-xl gap-px bg-border text-left sm:grid-cols-2">
      <div className="flex items-start gap-3 bg-card p-4">
        <CalendarHeart className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
        <div>
          <p className="eyebrow-sm text-muted-foreground">Week {pregnancy.current_week} · next check-up</p>
          <p className="mt-1 text-[13px] leading-snug">
            {visit ? `Around week ${visit.next_visit_week}` : "Ask me about your next visit"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3 bg-card p-4">
        <Droplets className="h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
        <div className="flex-1">
          <p className="eyebrow-sm text-muted-foreground">Water today</p>
          <p className="tabular mt-1 text-[13px]">{Math.round(waterMl / ML_PER_GLASS)} glasses</p>
        </div>
        <button
          type="button"
          onClick={addGlass}
          disabled={saving}
          className="eyebrow-sm h-9 border border-border px-3 text-foreground transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
        >
          + Glass
        </button>
      </div>
    </section>
  );
}
