"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { FeedbackReviewItem } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

function AdminFeedbackContent() {
  const [items, setItems] = React.useState<FeedbackReviewItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [onlyGaps, setOnlyGaps] = React.useState(false);

  React.useEffect(() => {
    api
      .get<FeedbackReviewItem[]>("/admin/feedback")
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load feedback."))
      .finally(() => setLoading(false));
  }, []);

  const shown = onlyGaps ? items.filter((i) => !i.had_evidence) : items;
  const gaps = items.filter((i) => !i.had_evidence).length;

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Answer feedback</h1>
        <p className="text-muted-foreground">
          Answers users rated down. Ones with no reviewed source are gaps in the knowledge base — add or approve a
          document that covers the question.
        </p>
      </div>

      <label className="flex w-fit items-center gap-2 text-sm">
        <input type="checkbox" checked={onlyGaps} onChange={(e) => setOnlyGaps(e.target.checked)} />
        Only knowledge gaps ({gaps})
      </label>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && <LoadingState label="Loading feedback..." />}
      {!loading && shown.length === 0 && <p className="text-sm text-muted-foreground">No low-rated answers. 🎉</p>}

      <div className="flex flex-col gap-4">
        {shown.map((item) => (
          <Card key={item.feedback_id}>
            <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
              <CardTitle className="text-base">{item.question ?? "(question not found)"}</CardTitle>
              <div className="flex shrink-0 gap-1.5">
                <Badge variant="destructive">{item.rating} / 5</Badge>
                <Badge variant={item.had_evidence ? "secondary" : "outline"}>
                  {item.had_evidence ? `${item.source_count} source${item.source_count === 1 ? "" : "s"}` : "no source"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {item.comment && <p className="text-sm">&ldquo;{item.comment}&rdquo;</p>}
              <details>
                <summary className="cursor-pointer text-sm text-muted-foreground">Show the answer given</summary>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{item.answer}</p>
              </details>
              <p className="text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}

export default function AdminFeedbackPage() {
  return (
    <RequireAuth adminOnly>
      <AdminFeedbackContent />
    </RequireAuth>
  );
}
