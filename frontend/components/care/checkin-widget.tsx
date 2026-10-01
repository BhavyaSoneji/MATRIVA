"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { Checkin, Triage } from "@/lib/care-types";
import { Button } from "@/components/ui/button";
import { Chip, Frame } from "@/components/care/frame";
import { TriageResult } from "@/components/care/triage";

const MOODS = [
  { v: 1, label: "Very low" },
  { v: 2, label: "Low" },
  { v: 3, label: "Okay" },
  { v: 4, label: "Good" },
  { v: 5, label: "Great" },
];
const MOVEMENT = [
  { v: "normal", label: "Normal" },
  { v: "reduced", label: "Less than usual" },
  { v: "not_yet", label: "Too early to feel" },
] as const;

/** The 30-second daily check-in: mood, symptoms, baby's movements, iron tablet. Warning signs trigger a safety result. */
export function CheckinWidget({ onDone }: { onDone?: () => void }) {
  const [mood, setMood] = React.useState<number | null>(null);
  const [symptoms, setSymptoms] = React.useState<string[]>([]);
  const [options, setOptions] = React.useState<string[]>([]);
  const [movement, setMovement] = React.useState<Checkin["baby_movement"]>(null);
  const [ifa, setIfa] = React.useState<boolean | null>(null);
  const [note, setNote] = React.useState("");
  const [saved, setSaved] = React.useState(false);
  const [triage, setTriage] = React.useState<Triage | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    api
      .get<{ checkin: Checkin | null; symptom_options: string[] }>("/care/checkin")
      .then((r) => {
        setOptions(r.symptom_options);
        if (r.checkin) {
          setMood(r.checkin.mood);
          setSymptoms(r.checkin.symptoms);
          setMovement(r.checkin.baby_movement);
          setIfa(r.checkin.ifa_taken);
          setNote(r.checkin.note ?? "");
        }
      })
      .catch(() => undefined);
  }, []);

  const toggle = (s: string) => setSymptoms((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.put<{ checkin: Checkin; triage: Triage | null }>("/care/checkin", {
        mood, symptoms, baby_movement: movement, ifa_taken: ifa, note: note || null,
      });
      setSaved(true);
      setTriage(res.triage);
      onDone?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save your check-in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Frame title="Today's check-in" note="Thirty seconds. Everything is optional.">
      <div className="flex flex-col gap-5">
        <div>
          <p className="eyebrow-sm mb-2 text-muted-foreground">How are you feeling?</p>
          <div className="flex flex-wrap gap-2">{MOODS.map((m) => <Chip key={m.v} active={mood === m.v} onClick={() => setMood(m.v)}>{m.label}</Chip>)}</div>
        </div>
        <div>
          <p className="eyebrow-sm mb-2 text-muted-foreground">Any symptoms today?</p>
          <div className="flex flex-wrap gap-2">{options.map((s) => <Chip key={s} active={symptoms.includes(s)} onClick={() => toggle(s)}>{s}</Chip>)}</div>
        </div>
        <div>
          <p className="eyebrow-sm mb-2 text-muted-foreground">Baby&apos;s movements</p>
          <div className="flex flex-wrap gap-2">{MOVEMENT.map((m) => <Chip key={m.v} active={movement === m.v} onClick={() => setMovement(m.v)}>{m.label}</Chip>)}</div>
        </div>
        <div>
          <p className="eyebrow-sm mb-2 text-muted-foreground">Iron + folic acid tablet taken today?</p>
          <div className="flex gap-2"><Chip active={ifa === true} onClick={() => setIfa(true)}>Yes</Chip><Chip active={ifa === false} onClick={() => setIfa(false)}>Not yet</Chip></div>
        </div>
        <label className="flex flex-col gap-1.5 text-[12px] text-muted-foreground">
          Anything to remember for your doctor? (optional)
          <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={2} className="border border-border bg-transparent p-2.5 text-sm text-foreground outline-none focus:border-accent" />
        </label>
        {error && <p className="text-sm text-blush-500">{error}</p>}
        <div className="flex items-center gap-4">
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : saved ? "Update check-in" : "Save check-in"}</Button>
          {saved && !triage && <span className="text-xs text-accent">Saved. Thank you.</span>}
        </div>
        {triage && <TriageResult result={triage} />}
      </div>
    </Frame>
  );
}
