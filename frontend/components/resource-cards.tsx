"use client";

import { ExternalLink, FileText, Landmark, Play, FlaskConical } from "lucide-react";
import type { ResourceResponse } from "@/lib/types";

const TYPE_LABEL: Record<ResourceResponse["type"], string> = {
  video: "Video",
  article: "Article",
  guideline: "Guideline",
  research: "Research",
};

function TypeIcon({ type }: { type: ResourceResponse["type"] }) {
  const cls = "h-3 w-3";
  if (type === "video") return <Play className={cls} aria-hidden="true" />;
  if (type === "research") return <FlaskConical className={cls} aria-hidden="true" />;
  if (type === "guideline") return <Landmark className={cls} aria-hidden="true" />;
  return <FileText className={cls} aria-hidden="true" />;
}

export function ResourceCard({ item }: { item: ResourceResponse }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noreferrer"
      className="lift group flex flex-col overflow-hidden border border-border bg-card"
    >
      {item.thumbnail ? (
        <div className="relative aspect-video w-full overflow-hidden bg-sage-100">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={item.thumbnail} alt="" loading="lazy" className="h-full w-full object-cover" />
          <span className="absolute inset-0 flex items-center justify-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-ink/70 text-cream-100 transition-transform group-hover:scale-110">
              <Play className="h-4 w-4 fill-current" aria-hidden="true" />
            </span>
          </span>
        </div>
      ) : null}
      <div className="flex flex-1 flex-col gap-1.5 p-3.5">
        <p className="eyebrow-sm flex items-center gap-1.5 text-accent">
          <TypeIcon type={item.type} />
          {TYPE_LABEL[item.type]}
          {item.language !== "en" && <span className="text-muted-foreground">· {item.language.toUpperCase()}</span>}
        </p>
        <p className="display text-[15px] leading-[1.25] group-hover:text-accent">{item.title}</p>
        <p className="text-[11.5px] leading-relaxed text-muted-foreground">{item.about}</p>
        <p className="mt-auto flex items-center gap-1.5 pt-2 text-[11px] text-muted-foreground">
          <span className="truncate">{item.publisher}</span>
          <ExternalLink className="ml-auto h-3 w-3 shrink-0" aria-hidden="true" />
        </p>
      </div>
    </a>
  );
}

export function ResourceGrid({ items, compact = false }: { items: ResourceResponse[]; compact?: boolean }) {
  if (items.length === 0) return null;
  return (
    <div className={`grid gap-3 ${compact ? "sm:grid-cols-3" : "sm:grid-cols-2 xl:grid-cols-3"}`}>
      {items.map((r) => (
        <ResourceCard key={r.id} item={r} />
      ))}
    </div>
  );
}
