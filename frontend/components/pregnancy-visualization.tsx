"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface PregnancyVisualizationProps {
  /** 1, 2, or 3 — drives the overall scale of the fetal silhouette. */
  trimester: number;
  /** 1-42ish — used for fine-grained scale within a trimester and the caption. */
  currentWeek?: number;
  /** "hero" renders larger with a caption baked in; "dashboard" is compact. */
  variant?: "hero" | "dashboard";
  className?: string;
}

/**
 * A tasteful, non-graphic, inline-SVG representation of the pregnant
 * abdomen/uterus with a simplified fetal silhouette inside. Entirely
 * presentational: scale is derived from the real PregnancyResponse
 * (trimester / current_week) the dashboard already fetches from the
 * backend. No external images or illustration libraries are used.
 *
 * This is intentionally abstract (a soft curl shape, not an anatomical
 * illustration) so it reads as calm/wellness rather than clinical or
 * cartoonish.
 */
export function PregnancyVisualization({
  trimester,
  currentWeek,
  variant = "dashboard",
  className,
}: PregnancyVisualizationProps) {
  const clampedTrimester = Math.min(3, Math.max(1, trimester || 1));
  const week = Math.min(42, Math.max(1, currentWeek ?? clampedTrimester * 13 - 6));

  // Base scale per trimester, refined slightly by week-within-trimester so the
  // silhouette grows continuously rather than jumping in three hard steps.
  const trimesterBase = { 1: 0.32, 2: 0.6, 3: 0.92 }[clampedTrimester] ?? 0.32;
  const weekFraction = Math.min(1, week / 40);
  const scale = Math.min(1, Math.max(0.28, trimesterBase + weekFraction * 0.12));

  const size = variant === "hero" ? 320 : 240;
  const label = { 1: "First trimester", 2: "Second trimester", 3: "Third trimester" }[clampedTrimester] ?? "";

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 border border-border bg-card p-6",
        className
      )}
    >
      <svg
        role="img"
        aria-label={`Illustration of pregnancy progression: ${label}, week ${week}`}
        width={size}
        height={size}
        viewBox="0 0 240 240"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <radialGradient id="wombGradient" cx="50%" cy="42%" r="65%">
            <stop offset="0%" stopColor="hsl(var(--sky-100))" />
            <stop offset="70%" stopColor="hsl(var(--sky-200))" />
            <stop offset="100%" stopColor="hsl(var(--sky-300))" />
          </radialGradient>
          <linearGradient id="babyGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="hsl(var(--sky-600))" />
            <stop offset="100%" stopColor="hsl(var(--sky-500))" />
          </linearGradient>
        </defs>

        {/* Outer frame: sharp rectangle, not a rounded card, to match the
            medical-chart aesthetic rather than a soft bubble. */}
        <rect x="4" y="4" width="232" height="232" fill="none" stroke="hsl(var(--border))" strokeWidth="1" />

        {/* Simplified abdomen / uterus silhouette. */}
        <ellipse cx="120" cy="132" rx="92" ry="86" fill="url(#wombGradient)" />
        <ellipse
          cx="120"
          cy="132"
          rx="92"
          ry="86"
          fill="none"
          stroke="hsl(var(--sky-400))"
          strokeWidth="1.5"
          strokeDasharray="2 5"
          opacity={0.6}
        />

        {/* Fetal silhouette: a simple curled comma/bean shape, abstract by
            design. Scales up with pregnancy progression around a fixed
            center so it visibly grows trimester to trimester. */}
        <g transform={`translate(120 136) scale(${scale}) translate(-60 -70)`}>
          <path
            d="M60 10
               C 92 10 112 34 112 62
               C 112 86 98 100 82 108
               C 96 114 106 126 104 140
               C 102 156 84 166 66 162
               C 48 158 32 144 24 126
               C 14 104 12 78 22 54
               C 30 32 42 10 60 10 Z"
            fill="url(#babyGradient)"
            opacity={0.92}
          />
          {/* head highlight */}
          <circle cx="70" cy="34" r="22" fill="hsl(var(--sky-700))" opacity={0.18} />
        </g>

        {/* Week tick mark on the frame, small medical-style annotation. */}
        <text
          x="16"
          y="224"
          fontSize="10"
          letterSpacing="0.08em"
          fill="hsl(var(--muted-foreground))"
          fontFamily="ui-sans-serif, system-ui"
        >
          WEEK {week}
        </text>
        <text
          x="224"
          y="224"
          fontSize="10"
          letterSpacing="0.08em"
          textAnchor="end"
          fill="hsl(var(--muted-foreground))"
          fontFamily="ui-sans-serif, system-ui"
        >
          T{clampedTrimester}
        </text>
      </svg>

      {variant === "hero" && (
        <div className="text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary">{label}</p>
          <p className="text-xs text-muted-foreground">Week {week} of 40</p>
        </div>
      )}
    </div>
  );
}
