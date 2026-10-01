import * as React from "react";

export interface GuardrailRule {
  id: string;
  kind: string;
  action: "escalate" | "block" | "caution";
  title: string;
  matched: string;
  sources: { key: string; name: string; url: string }[];
}

const ACTION_LABEL: Record<GuardrailRule["action"], string> = {
  escalate: "Emergency",
  block: "Not answered here",
  caution: "Caution",
};

export function guardrailsOf(m: { evidence?: Record<string, unknown> }): GuardrailRule[] {
  const g = m.evidence?.guardrails;
  return Array.isArray(g) ? (g as GuardrailRule[]) : [];
}

/** Which safety rules applied to this answer, and where each comes from. Collapsed by default. */
export function GuardrailNote({ rules }: { rules: GuardrailRule[] }) {
  if (rules.length === 0) return null;
  // one row per rule, keeping the most serious first
  const shown = rules.slice(0, 6);
  return (
    <details className="mt-3.5 border border-border bg-muted/40 text-sm">
      <summary className="eyebrow-sm cursor-pointer select-none px-3.5 py-2.5 text-accent">
        Why MATRIVA answered this way ({rules.length} safety {rules.length === 1 ? "rule" : "rules"})
      </summary>
      <ul className="flex flex-col gap-3 border-t border-border px-3.5 py-3">
        {shown.map((r) => (
          <li key={r.id} className="leading-relaxed">
            <span className="font-semibold">{r.title}</span>{" "}
            <span className="eyebrow-sm text-muted-foreground">· {ACTION_LABEL[r.action] ?? r.action}</span>
            {r.sources.length > 0 && (
              <span className="block text-xs text-muted-foreground">
                Based on:{" "}
                {r.sources.map((s, i) => (
                  <React.Fragment key={s.key}>
                    {i > 0 && "; "}
                    <a href={s.url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-accent">
                      {s.name}
                    </a>
                  </React.Fragment>
                ))}
              </span>
            )}
          </li>
        ))}
        <li className="text-xs text-muted-foreground">
          These rules run in MATRIVA itself, not in an AI model. Each names the reference it is based on, but a clinician or pharmacist has not yet checked each rule against that reference.
        </li>
      </ul>
    </details>
  );
}
