"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { GuidelineResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge } from "@/components/evidence-badge";
import { Badge } from "@/components/ui/badge";

function GuidanceContent() {
  const [guidelines, setGuidelines] = React.useState<GuidelineResponse[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .get<GuidelineResponse[]>("/guidelines")
      .then(setGuidelines)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load guidance."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Stage-wise guidance</h1>
        <p className="text-muted-foreground">Official guidelines from recognized health authorities.</p>
      </div>
      {loading && <LoadingState label="Loading guidelines..." />}
      {!loading && error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && guidelines.length === 0 && (
        <p className="text-sm text-muted-foreground">No active guidelines found.</p>
      )}
      <div className="flex flex-col gap-4">
        {guidelines.map((g) => (
          <Card key={g.id}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div>
                <CardTitle className="text-base">{g.authority}</CardTitle>
                <p className="text-xs text-muted-foreground">{g.jurisdiction}</p>
              </div>
              <Badge variant={g.status === "active" ? "success" : "warning"}>{g.status}</Badge>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <p className="text-sm text-foreground/90">{g.source.title}</p>
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {g.effective_date && <span>Effective: {g.effective_date}</span>}
                {g.version && <span>Version {g.version}</span>}
                <EvidenceBadge level={g.source.evidence_level} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}

export default function GuidancePage() {
  return (
    <RequireAuth>
      <GuidanceContent />
    </RequireAuth>
  );
}
