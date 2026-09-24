"use client";

import * as React from "react";
import { api, ApiError } from "@/lib/api";
import type { NextVisitResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge } from "@/components/evidence-badge";
import { CalendarHeart } from "lucide-react";

export function NextVisitCard() {
  const [data, setData] = React.useState<NextVisitResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    api
      .get<NextVisitResponse>("/pregnancy/next-visit")
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load your next visit.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 space-y-0">
        <CalendarHeart className="h-5 w-5 text-primary" />
        <CardTitle className="text-base">Next ANC visit</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && <LoadingState label="Loading..." />}
        {!loading && error && (
          <Alert variant="warning">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {!loading && data && (
          <div className="flex flex-col gap-2">
            <p className="text-2xl font-semibold text-foreground">Week {data.next_visit_week}</p>
            <p className="text-sm text-muted-foreground">{data.message}</p>
            <p className="text-xs text-muted-foreground">You are currently in week {data.current_week}.</p>
            <EvidenceBadge level={data.evidence_level} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
