"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Contact = { name: string; phone: string; relation: string | null } | null;

/** Settings card: how the pregnancy is dated, and who to call in an emergency. */
export function CareSettings() {
  const [mode, setMode] = React.useState<"lmp" | "edd">("lmp");
  const [date, setDate] = React.useState("");
  const [weight, setWeight] = React.useState("");
  const [name, setName] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [relation, setRelation] = React.useState("");
  const [msg, setMsg] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .get<{ contact: Contact }>("/care/emergency-contact")
      .then((r) => {
        if (r.contact) {
          setName(r.contact.name);
          setPhone(r.contact.phone);
          setRelation(r.contact.relation ?? "");
        }
      })
      .catch(() => undefined);
  }, []);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    setErr(null);
    try {
      await fn();
      setMsg(ok);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not save.");
    }
  };

  const saveDating = (e: React.FormEvent) => {
    e.preventDefault();
    void run(
      () =>
        api.put("/care/dating", {
          [mode === "lmp" ? "lmp_date" : "edd_date"]: date,
          ...(weight ? { pre_pregnancy_weight_kg: Number(weight) } : {}),
        }),
      "Dates saved. Your plan now follows them.",
    );
  };

  const saveContact = (e: React.FormEvent) => {
    e.preventDefault();
    void run(() => api.put("/care/emergency-contact", { name, phone, ...(relation ? { relation } : {}) }), "Emergency contact saved.");
  };

  const field = "h-10 border border-border bg-transparent px-3 text-sm outline-none focus:border-accent";
  return (
    <section className="border border-border p-7">
      <p className="eyebrow-sm text-accent">Dates & emergency contact</p>
      <p className="mt-1.5 text-sm text-muted-foreground">Exact dates give you an exact week, visit calendar and reminders. Requires consent.</p>

      <form onSubmit={saveDating} className="mt-5 flex flex-col gap-3">
        <div className="flex gap-2 text-[13px]">
          {(["lmp", "edd"] as const).map((m) => (
            <button key={m} type="button" onClick={() => setMode(m)} aria-pressed={mode === m}
              className={`eyebrow-sm min-h-9 border px-3 ${mode === m ? "border-accent text-accent" : "border-border text-muted-foreground"}`}>
              {m === "lmp" ? "Last period" : "Due date"}
            </button>
          ))}
        </div>
        <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className={field} aria-label={mode === "lmp" ? "First day of last period" : "Due date"} />
        <input inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="Weight before pregnancy, kg (optional)" className={field} />
        <Button type="submit" size="sm" disabled={!date}>Save dates</Button>
      </form>

      <form onSubmit={saveContact} className="mt-6 flex flex-col gap-3 border-t border-border pt-5">
        <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Emergency contact name" className={field} />
        <input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone number" inputMode="tel" className={field} />
        <input value={relation} onChange={(e) => setRelation(e.target.value)} placeholder="Relation (optional)" className={field} />
        <Button type="submit" size="sm" variant="outline" disabled={!name || phone.length < 5}>Save contact</Button>
      </form>
      {msg && <p className="mt-3 text-[13px] text-accent" role="status">{msg}</p>}
      {err && <p className="mt-3 text-[13px] text-blush-500" role="alert">{err}</p>}
    </section>
  );
}
