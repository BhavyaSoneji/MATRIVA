"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type {
  GraphNode,
  KnowledgeGraphResponse,
  PregnancyResponse,
  RecommendationResponse,
  ResourceLibraryResponse,
  ResourceResponse,
  WellnessLog,
  WellnessSummary,
} from "@/lib/types";
import { WeekRing } from "@/components/week-ring";
import { NextVisitCard } from "@/components/next-visit-card";
import { ResourceGrid } from "@/components/resource-cards";
import { EvidenceBadge, SafetyBadge } from "@/components/evidence-badge";
import { Button } from "@/components/ui/button";
import { Bookmark, BookmarkCheck, Droplets, Moon, Activity, Minus, Plus } from "lucide-react";

/** Inline cards the companion can show in the conversation. They replace what
 * used to be separate pages (dashboard, recommendations, evidence/sources). */
export type WidgetSpec =
  | { type: "week" }
  | { type: "visit" }
  | { type: "foryou" }
  | { type: "log" }
  | { type: "library"; topic?: string; types?: ResourceResponse["type"][] }
  | { type: "map"; q?: string };

const TRIMESTER_LABEL: Record<number, string> = { 1: "First", 2: "Second", 3: "Third" };

// General, widely-known pregnancy-education milestones per trimester; the
// backend has no per-week milestone endpoint.
const MILESTONES: Record<number, { title: string; detail: string }[]> = {
  1: [
    { title: "Major organs begin forming", detail: "The heart, brain and spinal cord start to develop." },
    { title: "Heartbeat may be detectable", detail: "Around week 6-8, on ultrasound." },
    { title: "Limb buds appear", detail: "Tiny arm and leg buds start to take shape." },
  ],
  2: [
    { title: "Movements may be felt", detail: "Many mothers notice fluttering movements." },
    { title: "Anatomy scan window", detail: "A detailed ultrasound is typically around week 18-20." },
    { title: "Hearing develops", detail: "Baby can start responding to sounds and voices." },
  ],
  3: [
    { title: "Rapid weight gain", detail: "Baby gains most of their birth weight now." },
    { title: "Lungs mature", detail: "Preparing for breathing outside the womb." },
    { title: "Head-down positioning", detail: "Baby typically settles head-down before delivery." },
  ],
};

function WidgetFrame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-border bg-card p-5">
      <h3 className="eyebrow mb-4 text-accent">{title}</h3>
      {children}
    </section>
  );
}

function WeekWidget({ pregnancy }: { pregnancy: PregnancyResponse | null }) {
  if (!pregnancy) {
    return (
      <WidgetFrame title="Your week">
        <p className="text-sm text-muted-foreground">
          Add your pregnancy details in Settings to see your week, trimester and milestones here.
        </p>
      </WidgetFrame>
    );
  }
  const trimester = Math.min(3, Math.max(1, pregnancy.trimester));
  return (
    <WidgetFrame title="Your week">
      <div className="flex flex-wrap items-center gap-8">
        <WeekRing week={pregnancy.current_week} size={150} />
        <div className="min-w-[200px] flex-1">
          <p className="eyebrow text-accent">{TRIMESTER_LABEL[trimester]} trimester</p>
          <p className="display mt-1 text-2xl capitalize">{pregnancy.stage.replace(/_/g, " ")}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {pregnancy.due_date ? `Due ${pregnancy.due_date}` : "Due date not set"} · {40 - pregnancy.current_week}{" "}
            weeks to go
          </p>
        </div>
      </div>
      <div className="mt-6 grid gap-px bg-border sm:grid-cols-3">
        {MILESTONES[trimester].map((m) => (
          <div key={m.title} className="bg-card p-4">
            <p className="display text-[16px] leading-[1.2]">{m.title}</p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">{m.detail}</p>
          </div>
        ))}
      </div>
    </WidgetFrame>
  );
}

function ForYouWidget() {
  const [items, setItems] = React.useState<RecommendationResponse[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let list = await api.get<RecommendationResponse[]>("/recommendations?limit=6");
        if (list.length === 0) list = await api.post<RecommendationResponse[]>("/recommendations/generate", { limit: 5 });
        if (!cancelled) setItems(list);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load recommendations.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleSave = async (item: RecommendationResponse) => {
    try {
      if (item.is_saved) await api.delete(`/recommendations/${item.id}/save`);
      else await api.post(`/recommendations/${item.id}/save`);
      setItems((prev) => prev.map((p) => (p.id === item.id ? { ...p, is_saved: !p.is_saved } : p)));
    } catch {
      // saving is a convenience; leave the card as-is on failure
    }
  };

  return (
    <WidgetFrame title="For you">
      {loading && <p className="text-sm text-muted-foreground">Finding suggestions for your stage…</p>}
      {error && <p className="text-sm text-blush-500">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Nothing to suggest yet — there are no reviewed documents matching your profile.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item.id} className="border border-border p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="eyebrow-sm text-accent">{item.domain}</p>
              <button
                type="button"
                aria-label={item.is_saved ? "Unsave" : "Save"}
                onClick={() => toggleSave(item)}
                className="text-accent hover:opacity-70"
              >
                {item.is_saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
              </button>
            </div>
            <p className="display mt-1.5 text-[17px] leading-[1.2]">{item.title}</p>
            <p className="mt-2 text-[12.5px] leading-relaxed text-muted-foreground">{item.description}</p>
            <p className="eyebrow-sm mt-3 text-accent">Why: {item.reason}</p>
            <div className="mt-3 flex flex-wrap gap-3 border-t border-border pt-3">
              <EvidenceBadge level={item.evidence_level} />
              <SafetyBadge status={item.safety_status} />
            </div>
          </div>
        ))}
      </div>
    </WidgetFrame>
  );
}

function Stepper({
  icon: Icon,
  label,
  value,
  step,
  max,
  unit,
  onChange,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  step: number;
  max: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="border border-border p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-4 w-4 text-accent" />
        <span className="eyebrow-sm">{label}</span>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          onClick={() => onChange(Math.max(0, +(value - step).toFixed(1)))}
          className="flex h-8 w-8 items-center justify-center border border-border hover:border-accent hover:text-accent"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <p className="display tabular text-2xl">
          {value}
          <span className="font-sans text-xs text-muted-foreground"> {unit}</span>
        </p>
        <button
          type="button"
          aria-label={`Increase ${label}`}
          onClick={() => onChange(Math.min(max, +(value + step).toFixed(1)))}
          className="flex h-8 w-8 items-center justify-center border border-border hover:border-accent hover:text-accent"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

const ML_PER_GLASS = 250;

function LogWidget() {
  const [glasses, setGlasses] = React.useState(0);
  const [sleep, setSleep] = React.useState(0);
  const [activity, setActivity] = React.useState(0);
  const [week, setWeek] = React.useState<WellnessLog[]>([]);
  const [state, setState] = React.useState<"idle" | "saving" | "saved" | "error">("idle");

  React.useEffect(() => {
    let cancelled = false;
    api
      .get<WellnessLog>("/wellness/daily")
      .then((log) => {
        if (cancelled) return;
        setGlasses(Math.round((log.water_intake_ml ?? 0) / ML_PER_GLASS));
        setSleep(log.sleep_hours ?? 0);
        setActivity(log.activity_minutes ?? 0);
      })
      .catch(() => undefined); // 404 = nothing logged today yet
    api
      .get<WellnessSummary>("/wellness/summary?days=7")
      .then((s) => !cancelled && setWeek(s.days))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const save = async () => {
    setState("saving");
    try {
      await api.put("/wellness/daily", {
        water_intake_ml: glasses * ML_PER_GLASS,
        sleep_hours: sleep,
        activity_minutes: activity,
      });
      setState("saved");
    } catch {
      setState("error");
    }
  };

  const bump = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setState("idle");
  };

  return (
    <WidgetFrame title="Log today">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stepper icon={Droplets} label="Water" value={glasses} step={1} max={20} unit="glasses" onChange={bump(setGlasses)} />
        <Stepper icon={Moon} label="Sleep" value={sleep} step={0.5} max={16} unit="hrs" onChange={bump(setSleep)} />
        <Stepper icon={Activity} label="Activity" value={activity} step={5} max={240} unit="min" onChange={bump(setActivity)} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <Button size="sm" onClick={save} disabled={state === "saving"}>
          {state === "saving" ? "Saving…" : "Save today"}
        </Button>
        {state === "saved" && <span className="text-xs text-accent">Saved.</span>}
        {state === "error" && <span className="text-xs text-blush-500">Could not save. Try again.</span>}
        <span className="text-[11px] text-muted-foreground">1 glass ≈ {ML_PER_GLASS} ml</span>
      </div>
      {week.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <p className="eyebrow-sm mb-3 text-muted-foreground">Last 7 days · sleep</p>
          <div className="flex h-14 items-end gap-1.5">
            {week.map((d) => (
              <div key={d.date} className="flex flex-1 flex-col items-center gap-1" title={`${d.date}: ${d.sleep_hours ?? 0} h`}>
                <div className="w-full bg-accent/70" style={{ height: `${Math.min(100, ((d.sleep_hours ?? 0) / 10) * 100)}%` }} />
                <span className="text-[9px] text-muted-foreground">{d.date.slice(8)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </WidgetFrame>
  );
}

function LibraryWidget({ spec, stage }: { spec: Extract<WidgetSpec, { type: "library" }>; stage?: string }) {
  const [topics, setTopics] = React.useState<Record<string, string>>({});
  const [topic, setTopic] = React.useState<string | undefined>(spec.topic);
  const [kind, setKind] = React.useState<ResourceResponse["type"] | "all">("all");
  const [items, setItems] = React.useState<ResourceResponse[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = new URLSearchParams({ limit: "60" });
    if (topic) params.set("topic", topic);
    if (kind !== "all") params.set("type", kind);
    if (stage) params.set("stage", stage);
    api
      .get<ResourceLibraryResponse>(`/resources?${params}`)
      .then((res) => {
        if (cancelled) return;
        setTopics(res.topics);
        setItems(
          spec.types && kind === "all" ? res.resources.filter((r) => spec.types!.includes(r.type)) : res.resources
        );
      })
      .catch(() => !cancelled && setItems([]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [topic, kind, stage, spec.types]);

  const chip = (active: boolean) =>
    `border px-3 py-1.5 text-[11.5px] transition-colors ${
      active ? "border-accent text-accent" : "border-border text-muted-foreground hover:border-accent hover:text-accent"
    }`;

  return (
    <WidgetFrame title={spec.types ? "Evidence & sources" : "Library"}>
      <div className="mb-3 flex flex-wrap gap-2">
        <button type="button" className={chip(!topic)} onClick={() => setTopic(undefined)}>
          All topics
        </button>
        {Object.entries(topics).map(([key, label]) => (
          <button key={key} type="button" className={chip(topic === key)} onClick={() => setTopic(key)}>
            {label}
          </button>
        ))}
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {(["all", "video", "article", "guideline", "research"] as const).map((k) => (
          <button key={k} type="button" className={chip(kind === k)} onClick={() => setKind(k)}>
            {k === "all" ? "Everything" : k[0].toUpperCase() + k.slice(1) + (k === "research" ? "" : "s")}
          </button>
        ))}
      </div>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing matches those filters.</p>
      ) : (
        <>
          <p className="mb-3 text-[11px] text-muted-foreground">
            {items.length} resources · links open the original publisher. Not a substitute for your care team.
          </p>
          <ResourceGrid items={items} />
        </>
      )}
    </WidgetFrame>
  );
}

const TYPE_COLOR: Record<string, string> = {
  nutrient: "hsl(var(--accent))",
  food: "hsl(var(--sage-300))",
  symptom: "hsl(var(--blush-500))",
  condition: "hsl(var(--blush-500) / 0.65)",
  practice: "hsl(var(--sky-500))",
  care: "hsl(var(--sky-700))",
  ayurveda: "hsl(var(--ink))",
  stage: "hsl(var(--sage-200))",
};

function layout(nodes: GraphNode[]): Record<string, { x: number; y: number }> {
  const W = 640;
  const H = 400;
  const cx = W / 2;
  const cy = H / 2;
  const focus = nodes.filter((n) => n.focus);
  const rest = nodes.filter((n) => !n.focus);
  const pos: Record<string, { x: number; y: number }> = {};
  focus.forEach((n, i) => {
    if (focus.length === 1) pos[n.id] = { x: cx, y: cy };
    else {
      const a = (i / focus.length) * Math.PI * 2 - Math.PI / 2;
      pos[n.id] = { x: cx + Math.cos(a) * 70, y: cy + Math.sin(a) * 52 };
    }
  });
  rest.forEach((n, i) => {
    const a = (i / Math.max(rest.length, 1)) * Math.PI * 2 - Math.PI / 2;
    pos[n.id] = { x: cx + Math.cos(a) * 235, y: cy + Math.sin(a) * 150 };
  });
  return pos;
}

function MapWidget({ q, onAsk }: { q?: string; onAsk?: (question: string) => void }) {
  const [graph, setGraph] = React.useState<KnowledgeGraphResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    api
      .get<KnowledgeGraphResponse>(`/knowledge/graph?q=${encodeURIComponent(q ?? "")}`)
      .then((g) => !cancelled && setGraph(g))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : "Could not load the map."));
    return () => {
      cancelled = true;
    };
  }, [q]);

  if (error) return <WidgetFrame title="Knowledge map"><p className="text-sm text-blush-500">{error}</p></WidgetFrame>;
  if (!graph) return <WidgetFrame title="Knowledge map"><p className="text-sm text-muted-foreground">Mapping…</p></WidgetFrame>;

  const pos = layout(graph.nodes);
  const presentTypes = Array.from(new Set(graph.nodes.map((n) => n.type)));
  return (
    <WidgetFrame title="Knowledge map">
      <svg viewBox="0 0 640 400" role="img" aria-label="Map of related topics" className="w-full">
        {graph.edges.map((e) => {
          const a = pos[e.source];
          const b = pos[e.target];
          if (!a || !b) return null;
          return (
            <line key={`${e.source}-${e.target}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="hsl(var(--border))" strokeWidth={1 + e.weight * 3} opacity={0.9}>
              <title>{`Mentioned together in ${e.passages} reviewed passages`}</title>
            </line>
          );
        })}
        {graph.nodes.map((n) => {
          const p = pos[n.id];
          const r = n.focus ? 17 : 11 + Math.min(n.passages, 40) / 8;
          return (
            <g
              key={n.id}
              transform={`translate(${p.x} ${p.y})`}
              tabIndex={0}
              role="button"
              aria-label={`Ask about ${n.label}`}
              className="cursor-pointer outline-none"
              onClick={() => onAsk?.(`Tell me about ${n.label}`)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onAsk?.(`Tell me about ${n.label}`)}
            >
              <circle r={r} fill={TYPE_COLOR[n.type] ?? "hsl(var(--sage-200))"} stroke={n.focus ? "hsl(var(--foreground))" : "none"} strokeWidth={1.5} />
              <text y={r + 13} textAnchor="middle" fontSize={11.5} fill="hsl(var(--foreground))">
                {n.label.length > 24 ? `${n.label.slice(0, 23)}…` : n.label}
              </text>
              <title>{`${n.label} — in ${n.passages} reviewed passages`}</title>
            </g>
          );
        })}
      </svg>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-muted-foreground">
        {presentTypes.map((t) => (
          <span key={t} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: TYPE_COLOR[t] ?? "hsl(var(--sage-200))" }} />
            {graph.types[t] ?? t}
          </span>
        ))}
        <span className="ml-auto">
          {graph.stats.passages.toLocaleString()} approved passages · links appear only when sources mention both topics · tap a topic to ask
        </span>
      </div>
    </WidgetFrame>
  );
}

export function ChatWidget({
  spec,
  pregnancy,
  onAsk,
}: {
  spec: WidgetSpec;
  pregnancy: PregnancyResponse | null;
  onAsk?: (question: string) => void;
}) {
  switch (spec.type) {
    case "week":
      return <WeekWidget pregnancy={pregnancy} />;
    case "visit":
      return <NextVisitCard />;
    case "foryou":
      return <ForYouWidget />;
    case "log":
      return <LogWidget />;
    case "library":
      return <LibraryWidget spec={spec} stage={pregnancy ? String(pregnancy.trimester) : undefined} />;
    case "map":
      return <MapWidget q={spec.q} onAsk={onAsk} />;
  }
}
