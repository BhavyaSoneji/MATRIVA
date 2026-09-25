"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, API_URL, getToken } from "@/lib/api";
import type { ProfileResponse, PregnancyResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CircleCheck, Download, Trash2 } from "lucide-react";

function SettingsContent() {
  const { logout } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = React.useState<ProfileResponse | null>(null);
  const [pregnancy, setPregnancy] = React.useState<PregnancyResponse | null>(null);
  const [fullName, setFullName] = React.useState("");
  const [region, setRegion] = React.useState("");
  const [dietType, setDietType] = React.useState("vegetarian");
  const [currentWeek, setCurrentWeek] = React.useState(8);
  const [dueDate, setDueDate] = React.useState("");
  const [firstPregnancy, setFirstPregnancy] = React.useState(true);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [deleteText, setDeleteText] = React.useState("");

  React.useEffect(() => {
    Promise.allSettled([api.get<ProfileResponse>("/profile"), api.get<PregnancyResponse>("/pregnancy")]).then(
      ([p, preg]) => {
        if (p.status === "fulfilled") {
          setProfile(p.value);
          setFullName(p.value.full_name || "");
          setRegion((p.value.cultural?.region as string) || "");
          setDietType((p.value.dietary?.diet_type as string) || "vegetarian");
        }
        if (preg.status === "fulfilled") {
          setPregnancy(preg.value);
          setCurrentWeek(preg.value.current_week);
          setDueDate(preg.value.due_date || "");
          setFirstPregnancy(preg.value.first_pregnancy);
        }
        setLoading(false);
      }
    );
  }, []);

  const saveProfile = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await api.put("/profile", {
        consent: true,
        full_name: fullName || undefined,
        region: region || undefined,
        diet_type: dietType,
      });
      await api.put("/pregnancy", {
        current_week: currentWeek,
        due_date: dueDate || undefined,
        first_pregnancy: firstPregnancy,
      });
      setMessage("Your details were saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your details.");
    } finally {
      setSaving(false);
    }
  };

  const exportData = async () => {
    setError(null);
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/privacy/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "matriva-export.json";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("Could not export your data. Please try again.");
    }
  };

  const deleteAccount = async () => {
    if (deleteText !== "DELETE") return;
    setError(null);
    try {
      await api.delete("/privacy/account");
      logout();
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete your account.");
    }
  };

  if (loading) return <LoadingState label="Loading settings..." />;

  return (
    <main className="mx-auto w-full max-w-[1400px] px-6 py-10">
      <div className="rise-in flex items-center gap-4 border-b border-border pb-9">
        <ManageIcon />
        <h1 className="display text-[2.5rem] leading-none">Settings</h1>
      </div>

      {message && (
        <Alert variant="success" className="mt-7">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert variant="destructive" className="mt-7">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        {/* profile */}
        <section className="border border-border p-8">
          <p className="eyebrow-sm text-accent">Profile & pregnancy</p>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {profile ? "Update your details below." : "You haven't set up your profile yet."}
          </p>

          <div className="mt-7 grid gap-6 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="fullName">Full name</Label>
              <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="region">Region</Label>
              <Input id="region" value={region} onChange={(e) => setRegion(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="diet">Dietary preference</Label>
              <Select id="diet" value={dietType} onChange={(e) => setDietType(e.target.value)}>
                <option value="vegetarian">Vegetarian</option>
                <option value="vegan">Vegan</option>
                <option value="non_vegetarian">Non-vegetarian</option>
                <option value="eggetarian">Eggetarian</option>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="week">Current pregnancy week</Label>
              <Input
                id="week"
                type="number"
                min={1}
                max={42}
                value={currentWeek}
                onChange={(e) => setCurrentWeek(Number(e.target.value))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dueDate">Due date</Label>
              <Input id="dueDate" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="first">First pregnancy?</Label>
              <Select
                id="first"
                value={firstPregnancy ? "yes" : "no"}
                onChange={(e) => setFirstPregnancy(e.target.value === "yes")}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </Select>
            </div>
          </div>

          <div className="mt-8 flex items-center justify-between border-t border-border pt-6">
            {pregnancy ? (
              <span className="eyebrow-sm bg-sage-100 px-3 py-1.5 text-sage-600">
                {pregnancy.stage.replace(/_/g, " ")} · Trimester {pregnancy.trimester}
              </span>
            ) : (
              <span />
            )}
            <Button onClick={saveProfile} disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </section>

        {/* consent + data */}
        <div className="flex flex-col gap-6">
          <section className="border border-border p-7">
            <p className="eyebrow-sm text-accent">Consent</p>
            <div className="mt-3 flex items-center gap-2.5">
              <CircleCheck
                className={`h-4 w-4 ${profile?.consent ? "text-sage-600" : "text-muted-foreground"}`}
                aria-hidden="true"
              />
              <p className="text-sm font-semibold">
                {profile?.consent ? "Data-sharing consent granted" : "Consent not granted"}
                {profile?.consent_version ? ` · v${profile.consent_version}` : ""}
              </p>
            </div>
            <div className="mt-5 flex gap-6">
              <button
                type="button"
                className="eyebrow-sm text-accent transition-opacity hover:opacity-70"
                onClick={async () => {
                  setError(null);
                  try {
                    await api.post("/privacy/consent", { granted: true, version: "2026-01" });
                    setProfile((p) => (p ? { ...p, consent: true, consent_version: "2026-01" } : p));
                    setMessage("Consent granted.");
                  } catch (err) {
                    setError(err instanceof ApiError ? err.message : "Could not update consent.");
                  }
                }}
              >
                Grant consent
              </button>
              <button
                type="button"
                className="eyebrow-sm text-blush-500 transition-opacity hover:opacity-70"
                onClick={async () => {
                  setError(null);
                  try {
                    await api.post("/privacy/consent", { granted: false, version: "2026-01" });
                    setProfile((p) => (p ? { ...p, consent: false } : p));
                    setMessage("Consent withdrawn.");
                  } catch (err) {
                    setError(err instanceof ApiError ? err.message : "Could not update consent.");
                  }
                }}
              >
                Withdraw consent
              </button>
            </div>
          </section>

          <section className="border border-border p-7">
            <p className="eyebrow-sm text-accent">Your data</p>

            <button
              type="button"
              onClick={exportData}
              className="mt-4 flex w-full items-center gap-2.5 border border-border bg-sage-100/60 px-4 py-3 text-sm font-semibold transition-colors hover:bg-sage-100"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              Export my data
            </button>

            <div className="mt-6 border-t border-border pt-5">
              <p className="eyebrow-sm text-blush-500">Danger zone</p>

              {!confirmDelete ? (
                <button
                  type="button"
                  onClick={() => setConfirmDelete(true)}
                  className="mt-3 flex w-full items-center gap-2.5 border border-blush-200 bg-blush-100 px-4 py-3 text-sm font-semibold text-blush-500 transition-colors hover:bg-blush-200"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Delete my account
                </button>
              ) : (
                <div className="mt-3 flex flex-col gap-3 border-l-2 border-blush-500 bg-blush-100 p-4">
                  <p className="text-sm leading-relaxed text-foreground/85">
                    This permanently deletes your account and all data. This cannot be undone. Type{" "}
                    <strong className="font-bold">DELETE</strong> to confirm.
                  </p>
                  <Input value={deleteText} onChange={(e) => setDeleteText(e.target.value)} placeholder="DELETE" />
                  <div className="flex gap-3">
                    <Button variant="destructive" disabled={deleteText !== "DELETE"} onClick={deleteAccount}>
                      Permanently delete
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setConfirmDelete(false);
                        setDeleteText("");
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
              <p className="mt-3 text-[11px] text-muted-foreground">Requires typing DELETE to confirm.</p>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

function ManageIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-7 w-7 text-accent"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 0 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 0 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 0 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 0 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z" />
    </svg>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsContent />
    </RequireAuth>
  );
}
