import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden px-6">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 h-[40rem] w-[40rem] -translate-x-1/2 -translate-y-1/2 animate-breathe rounded-full bg-[radial-gradient(circle,hsl(var(--sage-200)/0.5),transparent_68%)]"
      />
      <div className="relative rise-in text-center">
        <p className="eyebrow text-accent">404</p>
        <h1 className="display mt-5 text-[clamp(3rem,9vw,6rem)] leading-[0.95]">
          This page isn&apos;t
          <br />
          <span className="italic text-accent">in the record.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-sm text-sm leading-relaxed text-muted-foreground">
          Whatever you were looking for has moved, or never existed. Let&apos;s get you back to your week.
        </p>
        <div className="mt-10">
          <Link href="/dashboard">
            <Button size="lg">Back to your dashboard</Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
