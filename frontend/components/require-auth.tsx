"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { LoadingState } from "@/components/ui/spinner";

export function RequireAuth({
  children,
  adminOnly = false,
}: {
  children: React.ReactNode;
  adminOnly?: boolean;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!loading && !user) router.replace("/login");
    if (!loading && user && adminOnly && user.role !== "admin") router.replace("/dashboard");
  }, [loading, user, adminOnly, router]);

  if (loading || !user || (adminOnly && user.role !== "admin")) {
    return <LoadingState label="Checking your session..." />;
  }

  return <>{children}</>;
}
