"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { EvaluationResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

function AdminEvaluationContent() {
  const [results, setResults] = React.useState<EvaluationResponse[]>([]);
  const [suite, setSuite] = React.useState("all");
  const [loading, setLoading] = React.useState(true);
  const [running, setRunning] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setLoading(true);
    api
      .get<EvaluationResponse[]>("/evaluation/results")
      .then(setResults)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load evaluation results."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const runEvaluation = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await api.post<EvaluationResponse>("/evaluation/run", { suite });
      setResults((prev) => [res, ...prev]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start evaluation run.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Evaluation dashboard</h1>
        <p className="text-muted-foreground">Run and review automated evaluation suites.</p>
      </div>
      <div className="flex gap-2">
        <Select className="max-w-xs" value={suite} onChange={(e) => setSuite(e.target.value)}>
          <option value="all">All</option>
          <option value="retrieval">Retrieval</option>
          <option value="generation">Generation</option>
          <option value="safety">Safety</option>
        </Select>
        <Button onClick={runEvaluation} disabled={running}>
          {running ? "Running..." : "Run evaluation"}
        </Button>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && <LoadingState label="Loading results..." />}
      {!loading && results.length === 0 && <p className="text-sm text-muted-foreground">No evaluation runs yet.</p>}
      <div className="flex flex-col gap-4">
        {results.map((r) => (
          <Card key={r.id}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">{r.suite}</CardTitle>
              <Badge variant={r.status === "completed" || r.status === "passed" ? "success" : r.status === "failed" ? "destructive" : "secondary"}>
                {r.status}
              </Badge>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <p className="text-xs text-muted-foreground">
                Started: {new Date(r.started_at).toLocaleString()}
                {r.completed_at ? ` · Completed: ${new Date(r.completed_at).toLocaleString()}` : ""}
              </p>
              {r.error && <p className="text-destructive">{r.error}</p>}
              {Object.keys(r.metrics || {}).length > 0 && (
                <pre className="overflow-x-auto rounded bg-muted p-2 text-xs">
                  {JSON.stringify(r.metrics, null, 2)}
                </pre>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}

export default function AdminEvaluationPage() {
  return (
    <RequireAuth adminOnly>
      <AdminEvaluationContent />
    </RequireAuth>
  );
}
