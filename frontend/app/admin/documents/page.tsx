"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError, API_URL, getToken } from "@/lib/api";
import type { DocumentResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

function AdminDocumentsContent() {
  const [docs, setDocs] = React.useState<DocumentResponse[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [actioning, setActioning] = React.useState<string | null>(null);
  const [confirmReject, setConfirmReject] = React.useState<string | null>(null);
  const [uploadTitle, setUploadTitle] = React.useState("");
  const [uploadDomain, setUploadDomain] = React.useState("nutrition");
  const [uploadFile, setUploadFile] = React.useState<File | null>(null);
  const [uploading, setUploading] = React.useState(false);

  const load = React.useCallback(() => {
    setLoading(true);
    api
      .get<DocumentResponse[]>("/admin/documents")
      .then(setDocs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load documents."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const runAction = async (id: string, action: "approve" | "reject" | "reindex") => {
    setActioning(id + action);
    setError(null);
    try {
      const updated = await api.post<DocumentResponse>(`/admin/documents/${id}/${action}`);
      setDocs((prev) => prev.map((d) => (d.id === id ? updated : d)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not ${action} the document.`);
    } finally {
      setActioning(null);
      setConfirmReject(null);
    }
  };

  const uploadDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append(
        "metadata",
        JSON.stringify({ title: uploadTitle, domain: uploadDomain, language: "en" })
      );
      form.append("file", uploadFile);
      const token = getToken();
      const res = await fetch(`${API_URL}/admin/documents`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Upload failed");
      }
      const created = (await res.json()) as DocumentResponse;
      setDocs((prev) => [created, ...prev]);
      setUploadTitle("");
      setUploadFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload the document.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Document management</h1>
        <p className="text-muted-foreground">Review, approve, reject, and reindex knowledge documents.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Upload a document</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={uploadDocument}>
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="domain">Domain</Label>
              <Input id="domain" value={uploadDomain} onChange={(e) => setUploadDomain(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="file">File</Label>
              <input
                id="file"
                type="file"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="text-sm"
              />
            </div>
            <Button type="submit" disabled={uploading || !uploadFile}>
              {uploading ? "Uploading..." : "Upload"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && <LoadingState label="Loading documents..." />}
      {!loading && docs.length === 0 && <p className="text-sm text-muted-foreground">No documents found.</p>}
      <div className="flex flex-col gap-4">
        {docs.map((doc) => (
          <Card key={doc.id}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div>
                <CardTitle className="text-base">{doc.title}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {doc.domain} {doc.subdomain ? `/ ${doc.subdomain}` : ""} · {doc.language} · {doc.region || "global"}
                </p>
              </div>
              <div className="flex gap-1.5">
                <Badge variant={doc.review_status === "approved" ? "success" : doc.review_status === "rejected" ? "destructive" : "secondary"}>
                  {doc.review_status}
                </Badge>
                <Badge variant="outline">{doc.index_status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() => runAction(doc.id, "approve")}
                disabled={actioning === doc.id + "approve"}
              >
                Approve
              </Button>
              {confirmReject === doc.id ? (
                <>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => runAction(doc.id, "reject")}
                    disabled={actioning === doc.id + "reject"}
                  >
                    Confirm reject
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setConfirmReject(null)}>
                    Cancel
                  </Button>
                </>
              ) : (
                <Button size="sm" variant="outline" onClick={() => setConfirmReject(doc.id)}>
                  Reject
                </Button>
              )}
              <Button
                size="sm"
                variant="secondary"
                onClick={() => runAction(doc.id, "reindex")}
                disabled={actioning === doc.id + "reindex"}
              >
                Reindex
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}

export default function AdminDocumentsPage() {
  return (
    <RequireAuth adminOnly>
      <AdminDocumentsContent />
    </RequireAuth>
  );
}
