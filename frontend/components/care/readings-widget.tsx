"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import { API_URL, getToken } from "@/lib/api";
import type { Reading, ReadingCandidate, WeightGain } from "@/lib/care-types";
import { Button } from "@/components/ui/button";
import { Chip, Frame } from "@/components/care/frame";
import { Trash2, Upload } from "lucide-react";

const KINDS: { id: Reading["kind"]; label: string; unit: string }[] = [
  { id: "hb", label: "Haemoglobin", unit: "g/dL" },
  { id: "bp", label: "Blood pressure", unit: "mmHg" },
  { id: "weight", label: "Weight", unit: "kg" },
  { id: "glucose", label: "Blood sugar", unit: "mg/dL" },
];

function show(r: Reading) {
  return r.kind === "bp" ? `${r.systolic}/${r.diastolic}` : `${r.value}`;
}

function Trend({ rows, kind }: { rows: Reading[]; kind: Reading["kind"] }) {
  if (rows.length < 2) return null;
  const vals = rows.map((r) => (kind === "bp" ? (r.systolic ?? 0) : (r.value ?? 0)));
  const ref = kind === "hb" ? 11 : kind === "bp" ? 140 : null;
  const lo = Math.min(...vals, ref ?? Infinity) - 1;
  const hi = Math.max(...vals, ref ?? -Infinity) + 1;
  const x = (i: number) => 8 + (i / (rows.length - 1)) * 304;
  const y = (v: number) => 8 + (1 - (v - lo) / (hi - lo)) * 64;
  return (
    <svg viewBox="0 0 320 80" className="mt-3 w-full max-w-md" role="img" aria-label={`${kind} trend`}>
      {ref !== null && (
        <g>
          <line x1="8" x2="312" y1={y(ref)} y2={y(ref)} stroke="hsl(var(--blush-500))" strokeDasharray="3 3" opacity="0.6" />
          <text x="312" y={y(ref) - 3} textAnchor="end" fontSize="9" fill="hsl(var(--blush-500))">{kind === "hb" ? "11 (anaemia below)" : "140 (high at or above)"}</text>
        </g>
      )}
      <polyline fill="none" stroke="hsl(var(--accent))" strokeWidth="1.5" points={vals.map((v, i) => `${x(i)},${y(v)}`).join(" ")} />
      {vals.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r="2.8" fill="hsl(var(--accent))" />)}
    </svg>
  );
}

/** Health readings: add by hand, from pasted report text or a photo; see the trend and what each number means. */
export function ReadingsWidget() {
  const [kind, setKind] = React.useState<Reading["kind"]>("hb");
  const [rows, setRows] = React.useState<Reading[]>([]);
  const [gain, setGain] = React.useState<WeightGain | null>(null);
  const [v, setV] = React.useState("");
  const [sys, setSys] = React.useState("");
  const [dia, setDia] = React.useState("");
  const [context, setContext] = React.useState("fasting");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [reportText, setReportText] = React.useState("");
  const [cands, setCands] = React.useState<ReadingCandidate[]>([]);
  const [picked, setPicked] = React.useState<Set<number>>(new Set());
  const [info, setInfo] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    api
      .get<{ readings: Reading[]; weight_gain: WeightGain | null }>("/care/readings")
      .then((r) => {
        setRows(r.readings);
        setGain(r.weight_gain);
      })
      .catch(() => undefined);
  }, []);
  React.useEffect(load, [load]);

  const mine = rows.filter((r) => r.kind === kind);
  const unit = KINDS.find((k) => k.id === kind)!.unit;

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = kind === "bp" ? { kind, systolic: Number(sys), diastolic: Number(dia) } : { kind, value: Number(v), ...(kind === "glucose" ? { context } : {}) };
      await api.post("/care/readings", body);
      setV("");
      setSys("");
      setDia("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save that.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await api.delete(`/care/readings/${id}`).catch(() => undefined);
    load();
  };

  const parse = async () => {
    setError(null);
    setInfo(null);
    try {
      const r = await api.post<{ candidates: ReadingCandidate[] }>("/care/readings/parse-report", { text: reportText });
      setCands(r.candidates);
      setPicked(new Set(r.candidates.map((_, i) => i)));
      if (r.candidates.length === 0) setInfo("I could not find any haemoglobin, blood pressure, weight or sugar values in that text.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not read that text.");
    }
  };

  const upload = async (file: File) => {
    setError(null);
    setInfo("Reading the photo…");
    const form = new FormData();
    form.append("file", file);
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/care/readings/ocr`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not read that photo.");
      setReportText(data.text);
      setCands(data.candidates);
      setPicked(new Set(data.candidates.map((_: unknown, i: number) => i)));
      setInfo(data.candidates.length ? "Check each value against your report before saving." : "No values found. Try a clearer photo or paste the text.");
    } catch (err) {
      setInfo(null);
      setError(err instanceof Error ? err.message : "Could not read that photo.");
    }
  };

  const saveCandidates = async () => {
    setBusy(true);
    try {
      for (const i of picked) {
        const c = cands[i];
        await api.post("/care/readings", { kind: c.kind, date: c.date, value: c.value, systolic: c.systolic, diastolic: c.diastolic, context: c.context ?? undefined, source: "report" });
      }
      setCands([]);
      setReportText("");
      setInfo("Saved.");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Frame title="Health readings" note="Record numbers from your visits and see what they mean. Ask your doctor to interpret them.">
      <div className="mb-4 flex flex-wrap gap-2">{KINDS.map((k) => <Chip key={k.id} active={kind === k.id} onClick={() => setKind(k.id)}>{k.label}</Chip>)}</div>

      <form onSubmit={add} className="flex flex-wrap items-end gap-3">
        {kind === "bp" ? (
          <>
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">Top number<input inputMode="numeric" value={sys} onChange={(e) => setSys(e.target.value)} className="h-10 w-24 border border-border bg-transparent px-2 text-sm text-foreground" placeholder="120" /></label>
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">Bottom number<input inputMode="numeric" value={dia} onChange={(e) => setDia(e.target.value)} className="h-10 w-24 border border-border bg-transparent px-2 text-sm text-foreground" placeholder="80" /></label>
          </>
        ) : (
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">{KINDS.find((k) => k.id === kind)!.label} ({unit})<input inputMode="decimal" value={v} onChange={(e) => setV(e.target.value)} className="h-10 w-32 border border-border bg-transparent px-2 text-sm text-foreground" /></label>
        )}
        {kind === "glucose" && (
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">When
            <select value={context} onChange={(e) => setContext(e.target.value)} className="h-10 border border-border bg-transparent px-2 text-sm text-foreground">
              <option value="fasting">Fasting</option><option value="after_meal">After a meal</option><option value="random">Random</option>
            </select>
          </label>
        )}
        <Button type="submit" size="sm" disabled={busy}>Add today</Button>
      </form>
      {error && <p className="mt-3 text-sm text-blush-500">{error}</p>}

      <Trend rows={mine} kind={kind} />
      {kind === "weight" && gain && (
        <p className="mt-3 text-[12.5px] leading-relaxed">
          Gain so far: <strong>{gain.gain_kg} kg</strong> since your {gain.baseline} ({gain.baseline_kg} kg). {gain.note}
        </p>
      )}

      <ul className="mt-4 flex flex-col">
        {[...mine].reverse().map((r) => (
          <li key={r.id} className="border-t border-border py-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <span><span className="display tabular text-xl">{show(r)}</span> <span className="text-xs text-muted-foreground">{r.unit}{r.context ? ` · ${r.context.replace("_", " ")}` : ""} · {r.date}</span></span>
              <button type="button" aria-label="Delete reading" onClick={() => remove(r.id)} className="text-muted-foreground hover:text-blush-500"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
            {r.flags.map((f, i) => (
              <p key={i} className={`mt-1.5 border-l-2 pl-3 text-[12.5px] leading-snug ${f.level === "urgent" ? "border-blush-500 text-foreground" : "border-accent text-foreground/85"}`}>
                {f.message} <a href={f.url} target="_blank" rel="noreferrer" className="text-muted-foreground underline underline-offset-2 hover:text-accent">{f.source}</a>
              </p>
            ))}
          </li>
        ))}
        {mine.length === 0 && <li className="border-t border-border py-3 text-sm text-muted-foreground">Nothing recorded yet.</li>}
      </ul>

      <details className="mt-5 border-t border-border pt-4">
        <summary className="eyebrow-sm cursor-pointer text-muted-foreground hover:text-accent">Add from a lab report or prescription</summary>
        <div className="mt-3 flex flex-col gap-3">
          <textarea value={reportText} onChange={(e) => setReportText(e.target.value)} rows={4} placeholder="Paste the report text, e.g. Hb: 10.2 g/dL, BP 118/76 mmHg" className="border border-border bg-transparent p-2.5 text-sm outline-none focus:border-accent" />
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" variant="outline" onClick={parse} disabled={reportText.trim().length < 3}>Find values</Button>
            <label className="eyebrow-sm flex min-h-9 cursor-pointer items-center gap-1.5 border border-border px-3 text-muted-foreground hover:border-accent hover:text-accent">
              <Upload className="h-3 w-3" aria-hidden="true" /> Photo of report
              <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            </label>
          </div>
          {info && <p className="text-[12.5px] text-muted-foreground">{info}</p>}
          {cands.length > 0 && (
            <div className="border border-border p-3">
              <p className="eyebrow-sm mb-2 text-muted-foreground">Found — untick anything wrong, then save</p>
              <ul className="flex flex-col gap-1.5">
                {cands.map((c, i) => (
                  <li key={i}>
                    <label className="flex items-center gap-2.5 text-[13px]">
                      <input type="checkbox" checked={picked.has(i)} onChange={(e) => setPicked((p) => { const n = new Set(p); if (e.target.checked) n.add(i); else n.delete(i); return n; })} className="h-4 w-4 accent-[hsl(var(--accent))]" />
                      <span>{KINDS.find((k) => k.id === c.kind)?.label}: <strong>{c.kind === "bp" ? `${c.systolic}/${c.diastolic}` : c.value}</strong> on {c.date}</span>
                      <span className="text-[11px] text-muted-foreground">&ldquo;{c.matched}&rdquo;</span>
                    </label>
                  </li>
                ))}
              </ul>
              <Button size="sm" className="mt-3" onClick={saveCandidates} disabled={busy || picked.size === 0}>Save {picked.size} reading{picked.size === 1 ? "" : "s"}</Button>
            </div>
          )}
        </div>
      </details>
    </Frame>
  );
}
