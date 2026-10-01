import * as React from "react";

export function Frame({ title, children, note }: { title: string; children: React.ReactNode; note?: string }) {
  return (
    <section className="border border-border bg-card p-5">
      <h3 className="eyebrow mb-1 text-accent">{title}</h3>
      {note && <p className="mb-4 text-[12.5px] text-muted-foreground">{note}</p>}
      {!note && <div className="mb-3" />}
      {children}
    </section>
  );
}

export function Chip({ active, onClick, children, disabled }: { active: boolean; onClick: () => void; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={`min-h-9 border px-3 py-1.5 text-[12px] transition-colors ${
        active ? "border-accent bg-accent/10 text-accent" : "border-border text-muted-foreground hover:border-accent hover:text-accent"
      }`}
    >
      {children}
    </button>
  );
}
