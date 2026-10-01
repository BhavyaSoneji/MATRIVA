"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { DoctorSummary } from "@/lib/care-types";
import { Button } from "@/components/ui/button";
import { Printer } from "lucide-react";

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex gap-3 border-b border-border py-1.5 text-[13px]">
      <span className="w-40 shrink-0 text-muted-foreground">{k}</span>
      <span>{v}</span>
    </div>
  );
}

/** A one-page summary to show the doctor. "Print" saves it as a PDF through the browser's print dialog. */
export function SummaryWidget() {
  const [s, setS] = React.useState<DoctorSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    api.get<DoctorSummary>("/care/summary").then(setS).catch((e) => setError(e instanceof ApiError ? e.message : "Could not prepare the summary."));
  }, []);

  if (error) return <section className="border border-border bg-card p-5 text-sm text-blush-500">{error}</section>;
  if (!s) return <section className="border border-border bg-card p-5 text-sm text-muted-foreground">Preparing your summary…</section>;

  const r = s.readings.latest;
  return (
    <section className="print-sheet border border-border bg-card p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="eyebrow text-accent">Summary for my doctor</h3>
          <p className="display mt-1 text-2xl">{s.name ?? "Patient"} · prepared {s.generated_on}</p>
        </div>
        <Button size="sm" variant="outline" className="no-print" onClick={() => window.print()}><Printer className="h-3.5 w-3.5" aria-hidden="true" /> Print / PDF</Button>
      </div>

      {s.pregnancy && (
        <div className="mb-4">
          <Row k="Gestation" v={`Week ${s.pregnancy.week}, day ${s.pregnancy.day} (trimester ${s.pregnancy.trimester})`} />
          <Row k="Due date" v={`${s.pregnancy.edd} (dates from ${s.pregnancy.dates_from === "lmp" ? "last period" : s.pregnancy.dates_from === "edd" ? "due date" : "week entered"})`} />
          {s.pregnancy.next_visit && <Row k="Next visit" v={`around week ${s.pregnancy.next_visit.week} (${s.pregnancy.next_visit.date})`} />}
        </div>
      )}
      <Row k="Conditions" v={s.health.known_conditions.join(", ") || "none entered"} />
      <Row k="Allergies" v={s.health.allergies.join(", ") || "none entered"} />
      <Row k="Diet" v={s.health.diet ?? "not entered"} />

      <p className="eyebrow-sm mb-1 mt-5 text-muted-foreground">Latest readings</p>
      {Object.keys(r).length === 0 && <p className="text-[13px] text-muted-foreground">None recorded.</p>}
      {Object.values(r).map((x) => (
        <Row key={x.kind} k={x.kind === "bp" ? "Blood pressure" : x.kind === "hb" ? "Haemoglobin" : x.kind === "weight" ? "Weight" : "Blood sugar"}
          v={<>{x.kind === "bp" ? `${x.systolic}/${x.diastolic}` : x.value} {x.unit} <span className="text-muted-foreground">({x.date})</span>{x.flags.filter((f) => f.level !== "info").map((f, i) => <span key={i} className="ml-2 text-blush-500">⚑ {f.message}</span>)}</>} />
      ))}
      {s.readings.weight_gain && <Row k="Weight gain" v={`${s.readings.weight_gain.gain_kg} kg since ${s.readings.weight_gain.baseline}`} />}

      <p className="eyebrow-sm mb-1 mt-5 text-muted-foreground">Last {s.iron_tablets.days} days</p>
      <Row k="Check-ins" v={`${s.iron_tablets.checked_in} days`} />
      <Row k="Iron tablet" v={s.iron_tablets.ifa_answered ? `taken ${s.iron_tablets.ifa_taken} of ${s.iron_tablets.ifa_answered} days answered (streak ${s.iron_tablets.ifa_streak})` : "not recorded"} />
      <Row k="Symptoms" v={Object.entries(s.symptoms_last_14_days).map(([k, n]) => `${k} (${n} days)`).join(", ") || "none noted"} />
      {s.red_flags.length > 0 && <Row k="Warning signs" v={s.red_flags.map((f) => `${f.date}: ${f.flags.join(", ")}`).join("; ")} />}
      {s.nutrition && <Row k="Diet check" v={`${s.nutrition.days_logged} day(s) logged; lowest: ${s.nutrition.rows.slice(0, 2).map((x) => `${x.nutrient} ${x.percent}%`).join(", ")}`} />}

      {s.questions_for_doctor.length > 0 && (
        <>
          <p className="eyebrow-sm mb-2 mt-5 text-muted-foreground">Questions I would like to ask</p>
          <ol className="list-decimal pl-5 text-[13.5px] leading-relaxed">{s.questions_for_doctor.map((q, i) => <li key={i}>{q}</li>)}</ol>
        </>
      )}
      <p className="mt-5 text-[11px] text-muted-foreground">{s.disclaimer}</p>
    </section>
  );
}
