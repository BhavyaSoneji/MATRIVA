import { Badge } from "@/components/ui/badge";

const EVIDENCE_STYLES: Record<string, { label: string; variant: "success" | "warning" | "secondary" | "traditional" | "destructive" | "outline" }> = {
  supported: { label: "Supported", variant: "success" },
  mixed_evidence: { label: "Mixed evidence", variant: "warning" },
  limited_evidence: { label: "Limited evidence", variant: "warning" },
  preliminary: { label: "Preliminary", variant: "warning" },
  traditional: { label: "Traditional", variant: "traditional" },
  uncertain: { label: "Uncertain", variant: "secondary" },
  not_established: { label: "Not established", variant: "destructive" },
};

export function EvidenceBadge({ level }: { level: string | null | undefined }) {
  const info = EVIDENCE_STYLES[level ?? ""] ?? { label: level || "Unknown", variant: "outline" as const };
  return <Badge variant={info.variant}>{info.label}</Badge>;
}

const SAFETY_STYLES: Record<string, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
  safe_general: { label: "Safe (general)", variant: "success" },
  low_concern: { label: "Low concern", variant: "secondary" },
  medical_review: { label: "Needs medical review", variant: "warning" },
  high_risk: { label: "High risk", variant: "destructive" },
  urgent_escalation: { label: "Urgent — seek care", variant: "destructive" },
  insufficient_information: { label: "Insufficient information", variant: "secondary" },
};

export function SafetyBadge({ status }: { status: string | null | undefined }) {
  const info = SAFETY_STYLES[status ?? ""] ?? { label: status || "Unknown", variant: "secondary" as const };
  return <Badge variant={info.variant}>{info.label}</Badge>;
}
