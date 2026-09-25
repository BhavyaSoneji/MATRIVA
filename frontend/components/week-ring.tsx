"use client";

/** The stroke-draws-in circular week ring used on the dashboard and hero. */
export function WeekRing({
  week,
  size = 176,
  stroke = 3,
}: {
  week: number;
  size?: number;
  stroke?: number;
}) {
  const clamped = Math.min(40, Math.max(1, week));
  const r = size / 2 - stroke * 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - clamped / 40);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="h-full w-full -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="hsl(var(--sage-200))"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="hsl(var(--accent))"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="animate-draw"
          style={{ ["--dash" as string]: `${circumference}`, animationDelay: "0.5s" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="display tabular text-[2.75rem] leading-none">{clamped}</span>
        <span className="eyebrow-sm mt-1 text-muted-foreground">Weeks</span>
      </div>
    </div>
  );
}
