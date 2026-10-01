"use client";

import type { Triage } from "@/lib/care-types";
import { Phone, MapPin, TriangleAlert, CircleCheck } from "lucide-react";

const TONE: Record<Triage["level"], string> = {
  emergency: "border-blush-500 bg-blush-100",
  urgent: "border-blush-500/70 bg-blush-100/70",
  soon: "border-accent/60 bg-accent/5",
  none: "border-border bg-card",
};

/** The result of a red-flag check: what to do now, with one-tap ways to get help. Used by the check-in and /check. */
export function TriageResult({ result }: { result: Triage }) {
  const serious = result.level === "emergency" || result.level === "urgent";
  const Icon = serious ? TriangleAlert : CircleCheck;
  return (
    <div role="alert" className={`border-l-2 p-4 ${TONE[result.level]}`}>
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${serious ? "text-blush-500" : "text-accent"}`} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="display text-xl leading-tight">{result.title}</p>
          <p className="mt-1.5 text-sm leading-relaxed">{result.action}</p>
          {result.flagged.length > 0 && (
            <ul className="mt-3 flex flex-col gap-1.5 text-[12.5px]">
              {result.flagged.map((f) => (
                <li key={f.id}>
                  <span className="text-foreground">{f.text}</span>{" "}
                  <a href={f.url} target="_blank" rel="noreferrer" className="text-muted-foreground underline underline-offset-2 hover:text-accent">
                    {f.source}
                  </a>
                </li>
              ))}
            </ul>
          )}
          {(serious || result.level === "soon") && (
            <div className="mt-4 flex flex-wrap gap-2.5">
              {serious && (
                <a href={`tel:${result.emergency_numbers.general}`} className="inline-flex min-h-11 items-center gap-2 bg-blush-500 px-4 text-[12px] font-bold uppercase tracking-[0.08em] text-cream-100">
                  <Phone className="h-4 w-4" aria-hidden="true" /> Call {result.emergency_numbers.general}
                </a>
              )}
              {result.contact && (
                <a href={`tel:${result.contact.phone.replace(/\s/g, "")}`} className="inline-flex min-h-11 items-center gap-2 border border-border px-4 text-[12px] font-semibold hover:border-accent hover:text-accent">
                  <Phone className="h-4 w-4" aria-hidden="true" /> Call {result.contact.name}
                </a>
              )}
              {serious && (
                <a href={result.maps_url} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 border border-border px-4 text-[12px] font-semibold hover:border-accent hover:text-accent">
                  <MapPin className="h-4 w-4" aria-hidden="true" /> Find a hospital
                </a>
              )}
            </div>
          )}
          {serious && result.emergency_numbers.ambulance.length > 0 && (
            <p className="mt-3 text-[11.5px] text-muted-foreground">Ambulance: {result.emergency_numbers.ambulance.join(" / ")}</p>
          )}
          <p className="mt-3 text-[11px] text-muted-foreground">{result.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}
