import { Badge } from "@/components/ui/badge";

type Variant = "success" | "warning" | "secondary" | "traditional" | "destructive" | "outline";

/* Glyph carries the meaning; hue only reinforces it. */
const EVIDENCE_STYLES: Record<string, { label: string; variant: Variant; glyph: string }> = {
  supported: { label: "Supported", variant: "success", glyph: "◆" },
  mixed_evidence: { label: "Mixed evidence", variant: "warning", glyph: "◇" },
  limited_evidence: { label: "Limited evidence", variant: "warning", glyph: "◇" },
  preliminary: { label: "Preliminary", variant: "warning", glyph: "◇" },
  traditional: { label: "Traditional", variant: "traditional", glyph: "○" },
  uncertain: { label: "Uncertain", variant: "secondary", glyph: "○" },
  not_established: { label: "Not established", variant: "destructive", glyph: "▲" },
};

export function EvidenceBadge({ level }: { level: string | null | undefined }) {
  const info =
    EVIDENCE_STYLES[level ?? ""] ??
    { label: level || "Unknown", variant: "outline" as const, glyph: "·" };
  return (
    <Badge variant={info.variant}>
      <span aria-hidden="true">{info.glyph}</span>
      {info.label}
    </Badge>
  );
}

const SAFETY_STYLES: Record<string, { label: string; variant: Variant; glyph: string }> = {
  safe_general: { label: "Safe (general)", variant: "success", glyph: "◆" },
  low_concern: { label: "Low concern", variant: "secondary", glyph: "○" },
  medical_review: { label: "Needs medical review", variant: "warning", glyph: "◇" },
  high_risk: { label: "High risk", variant: "destructive", glyph: "▲" },
  urgent_escalation: { label: "Urgent — seek care", variant: "destructive", glyph: "▲" },
  insufficient_information: { label: "Insufficient information", variant: "secondary", glyph: "○" },
};

export function SafetyBadge({ status }: { status: string | null | undefined }) {
  const info =
    SAFETY_STYLES[status ?? ""] ??
    { label: status || "Unknown", variant: "secondary" as const, glyph: "·" };
  return (
    <Badge variant={info.variant}>
      <span aria-hidden="true">{info.glyph}</span>
      {info.label}
    </Badge>
  );
}
