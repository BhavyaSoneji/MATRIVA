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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";

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
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-10">
      <h1 className="text-2xl font-semibold text-foreground">Settings</h1>

      {message && (
        <Alert variant="success">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Profile & pregnancy</CardTitle>
          <CardDescription>
            {profile ? "Update your details below." : "You haven't set up your profile yet."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
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
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="first">First pregnancy?</Label>
            <Select id="first" value={firstPregnancy ? "yes" : "no"} onChange={(e) => setFirstPregnancy(e.target.value === "yes")}>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </Select>
          </div>
          {pregnancy && (
            <p className="text-xs text-muted-foreground">
              Current stage: {pregnancy.stage} (trimester {pregnancy.trimester})
            </p>
          )}
          <Button onClick={saveProfile} disabled={saving}>
            {saving ? "Saving..." : "Save changes"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Consent</CardTitle>
          <CardDescription>
            Consent status: {profile?.consent ? "granted" : "not granted"}
            {profile?.consent_version ? ` (v${profile.consent_version})` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button
            variant="outline"
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
          </Button>
          <Button
            variant="outline"
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
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Your data</CardTitle>
          <CardDescription>Export your data or permanently delete your account.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Button variant="outline" onClick={exportData}>
            Export my data
          </Button>

          {!confirmDelete ? (
            <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
              Delete my account
            </Button>
          ) : (
            <div className="flex flex-col gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-4">
              <p className="text-sm text-destructive">
                This permanently deletes your account and all data. This cannot be undone. Type{" "}
                <strong>DELETE</strong> to confirm.
              </p>
              <Input value={deleteText} onChange={(e) => setDeleteText(e.target.value)} placeholder="DELETE" />
              <div className="flex gap-2">
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
        </CardContent>
      </Card>
    </main>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsContent />
    </RequireAuth>
  );
}
