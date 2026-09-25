"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { LifestyleItem } from "@/lib/types";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge, SafetyBadge } from "@/components/evidence-badge";

function LifestyleContent() {
  const [items, setItems] = React.useState<LifestyleItem[]>([]);
  const [category, setCategory] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback((cat: string) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (cat) params.set("category", cat);
    api
      .get<LifestyleItem[]>(`/knowledge/lifestyle?${params.toString()}`)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load lifestyle guidance."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    load("");
  }, [load]);

  const categories = Array.from(new Set(items.map((i) => i.category)));

  return (
    <main className="mx-auto w-full max-w-[1400px] px-6 py-10">
      <div className="rise-in border-b border-border pb-9">
        <p className="eyebrow text-accent">Lifestyle</p>
        <h1 className="display mt-3 text-[2.5rem] leading-none">Movement, rest, rhythm.</h1>
        <p className="mt-3 text-sm text-muted-foreground">Exercise and lifestyle recommendations for pregnancy.</p>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-2.5">
        <span className="eyebrow-sm text-muted-foreground">Category:</span>
        <button
          type="button"
          onClick={() => {
            setCategory("");
            load("");
          }}
          className={`eyebrow-sm border px-3.5 py-2 transition-colors ${
            category === "" ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:border-accent hover:text-accent"
          }`}
        >
          All
        </button>
        {categories.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => {
              setCategory(c);
              load(c);
            }}
            className={`eyebrow-sm border px-3.5 py-2 transition-colors ${
              category === c ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:border-accent hover:text-accent"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {loading && <LoadingState label="Loading lifestyle guidance..." />}
      {!loading && error && (
        <Alert variant="destructive" className="mt-8">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">No lifestyle guidance found.</p>
      )}

      <div className="mt-8 grid gap-px bg-border sm:grid-cols-2">
        {items.map((item) => (
          <div key={item.id} className="bg-background p-7">
            <p className="eyebrow-sm text-accent">{item.category}</p>
            <h2 className="display mt-2.5 text-2xl leading-[1.15]">{item.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.description}</p>
            {item.restrictions.length > 0 && (
              <p className="mt-3 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">Avoid if:</span> {item.restrictions.join(", ")}
              </p>
            )}
            <div className="mt-5 flex flex-wrap gap-4 border-t border-border pt-4">
              <EvidenceBadge level={item.evidence_status} />
              <SafetyBadge status={item.safety_status} />
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

export default function LifestylePage() {
  return (
    <RequireAuth>
      <LifestyleContent />
    </RequireAuth>
  );
}
