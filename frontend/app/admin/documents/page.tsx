"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError, API_URL, getToken } from "@/lib/api";
import type { BulkApproveResult, DocumentPreview, DocumentResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

type Tab = "pending" | "approved" | "rejected" | "all";

const TABS: { id: Tab; label: string }[] = [
  { id: "pending", label: "To review" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
  { id: "all", label: "All" },
];

function matchesTab(doc: DocumentResponse, tab: Tab) {
  if (tab === "all") return true;
  if (tab === "pending") return doc.review_status !== "approved" && doc.review_status !== "rejected";
  return doc.review_status === tab;
}

function Preview({ id }: { id: string }) {
  const [data, setData] = React.useState<DocumentPreview | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    api
      .get<DocumentPreview>(`/admin/documents/${id}/preview`)
      .then((res) => !cancelled && setData(res))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : "Could not load the preview."));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data) return <p className="text-sm text-muted-foreground">Loading preview…</p>;
  return (
    <div className="flex flex-col gap-3 border-l-2 border-border pl-4">
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        {data.excerpt || "No text stored for this document."}
      </p>
      <p className="text-xs text-muted-foreground">
        {data.chunk_count} passage{data.chunk_count === 1 ? "" : "s"}
        {data.truncated ? " (first few shown)" : ""}
        {data.authority ? ` · ${data.authority}` : ""}
      </p>
      {data.source_url && (
        <a
          href={data.source_url}
          target="_blank"
          rel="noreferrer"
          className="w-fit text-sm text-accent underline underline-offset-2"
        >
          Check against the original source →
        </a>
      )}
    </div>
  );
}

function AdminDocumentsContent() {
  const [docs, setDocs] = React.useState<DocumentResponse[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [actioning, setActioning] = React.useState<string | null>(null);
  const [confirmReject, setConfirmReject] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<Tab>("pending");
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [open, setOpen] = React.useState<string | null>(null);
  const [showUpload, setShowUpload] = React.useState(false);
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

  const counts = React.useMemo(() => {
    const c: Record<Tab, number> = { pending: 0, approved: 0, rejected: 0, all: docs.length };
    for (const d of docs) {
      if (d.review_status === "approved") c.approved++;
      else if (d.review_status === "rejected") c.rejected++;
      else c.pending++;
    }
    return c;
  }, [docs]);

  const visible = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return docs.filter(
      (d) => matchesTab(d, tab) && (!q || `${d.title} ${d.domain} ${d.source.authority ?? ""}`.toLowerCase().includes(q))
    );
  }, [docs, tab, query]);

  const approvable = visible.filter((d) => d.review_status !== "approved" && d.index_status === "indexed");
  const selectedApprovable = approvable.filter((d) => selected.has(d.id));

  const runAction = async (id: string, action: "approve" | "reject" | "reindex") => {
    setActioning(id + action);
    setError(null);
    setNotice(null);
    try {
      const updated = await api.post<DocumentResponse>(`/admin/documents/${id}/${action}`);
      setDocs((prev) => prev.map((d) => (d.id === id ? updated : d)));
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not ${action} the document.`);
    } finally {
      setActioning(null);
      setConfirmReject(null);
    }
  };

  const bulkApprove = async () => {
    const ids = selectedApprovable.map((d) => d.id);
    if (ids.length === 0) return;
    setActioning("bulk");
    setError(null);
    setNotice(null);
    try {
      const res = await api.post<BulkApproveResult>("/admin/documents/bulk-approve", { ids });
      const skipped = Object.keys(res.skipped).length;
      setNotice(`Approved ${res.approved.length} document${res.approved.length === 1 ? "" : "s"}${skipped ? `, skipped ${skipped}` : ""}.`);
      setSelected(new Set());
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not approve the selected documents.");
    } finally {
      setActioning(null);
    }
  };

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const uploadDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("metadata", JSON.stringify({ title: uploadTitle, domain: uploadDomain, language: "en" }));
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
      setShowUpload(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload the document.");
    } finally {
      setUploading(false);
    }
  };

  const tabClass = (active: boolean) =>
    `border px-3.5 py-2 text-[12px] transition-colors ${
      active ? "border-accent text-accent" : "border-border text-muted-foreground hover:border-accent hover:text-accent"
    }`;

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Review queue</h1>
          <p className="text-muted-foreground">
            Only approved documents can ground chat answers. Read the text, check it against the source, then approve.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setShowUpload((v) => !v)}>
          {showUpload ? "Close upload" : "Upload a document"}
        </Button>
      </div>

      {showUpload && (
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
                <input id="file" type="file" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} className="text-sm" />
              </div>
              <Button type="submit" disabled={uploading || !uploadFile}>
                {uploading ? "Uploading..." : "Upload"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button key={t.id} type="button" className={tabClass(tab === t.id)} onClick={() => setTab(t.id)}>
            {t.label} <span className="tabular opacity-70">{counts[t.id]}</span>
          </button>
        ))}
        <Input
          aria-label="Search documents"
          placeholder="Search title, domain, authority"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="ml-auto max-w-xs"
        />
      </div>

      {approvable.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 border border-border bg-card px-4 py-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selectedApprovable.length === approvable.length}
              onChange={(e) => setSelected(e.target.checked ? new Set(approvable.map((d) => d.id)) : new Set())}
            />
            Select all {approvable.length} ready to approve
          </label>
          <Button size="sm" className="ml-auto" disabled={selectedApprovable.length === 0 || actioning === "bulk"} onClick={bulkApprove}>
            {actioning === "bulk" ? "Approving…" : `Approve selected (${selectedApprovable.length})`}
          </Button>
        </div>
      )}

      {notice && (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && <LoadingState label="Loading documents..." />}
      {!loading && visible.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {tab === "pending" ? "Nothing waiting for review." : "No documents match."}
        </p>
      )}

      <div className="flex flex-col gap-4">
        {visible.map((doc) => {
          const canApprove = doc.index_status === "indexed";
          return (
            <Card key={doc.id}>
              <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
                <div className="flex items-start gap-3">
                  {doc.review_status !== "approved" && canApprove && (
                    <input
                      type="checkbox"
                      aria-label={`Select ${doc.title}`}
                      className="mt-1"
                      checked={selected.has(doc.id)}
                      onChange={() => toggle(doc.id)}
                    />
                  )}
                  <div>
                    <CardTitle className="text-base">{doc.title}</CardTitle>
                    <p className="text-xs text-muted-foreground">
                      {doc.domain} {doc.subdomain ? `/ ${doc.subdomain}` : ""} · {doc.language} · {doc.region || "any region"}
                      {doc.source.authority ? ` · ${doc.source.authority}` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <Badge variant={doc.review_status === "approved" ? "success" : doc.review_status === "rejected" ? "destructive" : "secondary"}>
                    {doc.review_status}
                  </Badge>
                  <Badge variant="outline">{doc.index_status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {open === doc.id && <Preview id={doc.id} />}
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => setOpen(open === doc.id ? null : doc.id)}>
                    {open === doc.id ? "Hide text" : "Read text"}
                  </Button>
                  {doc.review_status !== "approved" && (
                    <Button
                      size="sm"
                      onClick={() => runAction(doc.id, "approve")}
                      disabled={!canApprove || actioning === doc.id + "approve"}
                      title={canApprove ? undefined : "Reindex first — only indexed documents can be approved"}
                    >
                      Approve
                    </Button>
                  )}
                  {doc.review_status !== "rejected" &&
                    (confirmReject === doc.id ? (
                      <>
                        <Button size="sm" variant="destructive" onClick={() => runAction(doc.id, "reject")} disabled={actioning === doc.id + "reject"}>
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
                    ))}
                  <Button size="sm" variant="secondary" onClick={() => runAction(doc.id, "reindex")} disabled={actioning === doc.id + "reindex"}>
                    Reindex
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
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
