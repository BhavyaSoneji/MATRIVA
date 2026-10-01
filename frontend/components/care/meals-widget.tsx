"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { MealsDay } from "@/lib/care-types";
import { Button } from "@/components/ui/button";
import { Chip, Frame } from "@/components/care/frame";
import { Trash2 } from "lucide-react";

const TYPES = ["breakfast", "lunch", "dinner", "snack"] as const;
const NICE: Record<string, string> = { "folate (DFE)": "folate", "vitamin C": "vitamin C" };

/** Meal log: type what you ate, see how today compares with a pregnancy allowance and what would fill the gaps. */
export function MealsWidget() {
  const [day, setDay] = React.useState<MealsDay | null>(null);
  const [text, setText] = React.useState("");
  const [type, setType] = React.useState<(typeof TYPES)[number] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [info, setInfo] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(() => {
    api.get<MealsDay>("/care/meals").then(setDay).catch(() => undefined);
  }, []);
  React.useEffect(load, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const r = await api.post<{ not_understood: string[] }>("/care/meals", { text, ...(type ? { meal_type: type } : {}) });
      setText("");
      if (r.not_understood.length) setInfo(`Not recognised: ${r.not_understood.join("; ")}`);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log that.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await api.delete(`/care/meals/${id}`).catch(() => undefined);
    load();
  };

  return (
    <Frame title="What I ate today" note='Type it the way you say it: "2 roti, 1 katori dal, curd, a banana". Portions are approximate.'>
      <form onSubmit={add} className="flex flex-col gap-3">
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={500} placeholder="2 roti, 1 katori dal, curd" className="h-11 border border-border bg-transparent px-3 text-sm outline-none focus:border-accent" aria-label="What did you eat?" />
        <div className="flex flex-wrap items-center gap-2">
          {TYPES.map((t) => <Chip key={t} active={type === t} onClick={() => setType(type === t ? null : t)}>{t}</Chip>)}
          <Button type="submit" size="sm" className="ml-auto" disabled={busy || text.trim().length < 2}>Add meal</Button>
        </div>
      </form>
      {error && <p className="mt-3 text-sm text-blush-500">{error}</p>}
      {info && <p className="mt-3 text-[12.5px] text-muted-foreground">{info}</p>}

      {day && (
        <>
          <ul className="mt-4 flex flex-col">
            {day.meals.map((m) => (
              <li key={m.id} className="flex items-start justify-between gap-3 border-t border-border py-2.5 text-[13px]">
                <span>
                  {m.meal_type && <span className="eyebrow-sm mr-2 text-accent">{m.meal_type}</span>}
                  {m.items.map((i) => `${i.name.split(" (")[0]} ${i.grams} g`).join(" · ")}
                </span>
                <button type="button" aria-label="Delete meal" onClick={() => remove(m.id)} className="shrink-0 text-muted-foreground hover:text-blush-500"><Trash2 className="h-3.5 w-3.5" /></button>
              </li>
            ))}
            {day.meals.length === 0 && <li className="border-t border-border py-3 text-sm text-muted-foreground">Nothing logged today.</li>}
          </ul>

          {day.meals.length > 0 && (
            <div className="mt-4 border-t border-border pt-4">
              <p className="eyebrow-sm mb-3 text-muted-foreground">Today vs a pregnancy day</p>
              <div className="flex flex-col gap-2.5">
                {day.rows.map((r) => (
                  <div key={r.nutrient} className="flex items-center gap-3 text-[12.5px]">
                    <span className="w-20 shrink-0 text-muted-foreground">{NICE[r.nutrient] ?? r.nutrient}</span>
                    <div className="h-[5px] flex-1 bg-sage-100" role="img" aria-label={`${r.nutrient} ${r.percent}% of the allowance`}>
                      <div className={`h-full ${r.percent >= 70 ? "bg-accent" : "bg-blush-500"}`} style={{ width: `${Math.min(100, r.percent)}%` }} />
                    </div>
                    <span className="tabular w-24 shrink-0 text-right">{r.percent}% <span className="text-muted-foreground">of {r.target}</span></span>
                  </div>
                ))}
              </div>
              {day.suggestions.map((s) => (
                <p key={s.nutrient} className="mt-3 text-[12.5px] leading-relaxed">
                  <strong>To add {NICE[s.nutrient] ?? s.nutrient}:</strong> {s.foods.map((f) => `${f.name.split(" (")[0]} (${f.serving_g} g gives ${f.amount})`).join(", ")}.
                </p>
              ))}
              <p className="mt-3 text-[11px] text-muted-foreground">{day.note}</p>
            </div>
          )}
        </>
      )}
    </Frame>
  );
}
