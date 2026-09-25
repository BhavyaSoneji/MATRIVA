import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";

const authorities = [
  "World Health Organization",
  "ICMR",
  "FOGSI",
  "ACOG",
  "NICE",
  "RCOG",
  "Charaka Samhita",
];

const pillars = [
  {
    index: "01",
    title: "Every claim carries its source",
    body: "Answers cite the guideline they came from, with the evidence level stated plainly — supported, mixed, traditional, or needing review. You can open the source and read it yourself.",
  },
  {
    index: "02",
    title: "Safety is checked before you see it",
    body: "Anything that resembles a danger sign is escalated in the answer itself, not buried below it. MATRIVA will tell you to call your provider today when that is the right advice.",
  },
  {
    index: "03",
    title: "Tradition, labelled as tradition",
    body: "Ayurvedic practice sits alongside clinical guidance and is never dressed up as trial evidence. You see which is which, every time.",
  },
  {
    index: "04",
    title: "Built around your week",
    body: "Region, diet, trimester and history shape what surfaces. Week 24 in a South Indian vegetarian kitchen is a different conversation from week 9.",
  },
];

function Ticker() {
  return (
    <div className="flex w-max animate-marquee items-center">
      {[0, 1].map((copy) => (
        <div
          key={copy}
          aria-hidden={copy === 1}
          className="eyebrow flex items-center gap-11 pr-11 text-muted-foreground"
        >
          {authorities.map((name) => (
            <span key={name} className="flex items-center gap-11 whitespace-nowrap">
              {name}
              <span className="text-sage-400" aria-hidden="true">
                ◆
              </span>
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  return (
    <main className="flex flex-col">
      {/* ── hero ─────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-border">
        {/* soft light washes */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-40 -top-24 h-[52rem] w-[52rem] animate-breathe rounded-full bg-[radial-gradient(circle,hsl(var(--sage-200)/0.62),hsl(var(--sage-100)/0.28)_46%,transparent_68%)]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-72 -left-44 h-[50rem] w-[50rem] rounded-full bg-[radial-gradient(circle,hsl(var(--blush-100)/0.85),transparent_66%)]"
        />

        {/* the grid, visible on purpose */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 mx-auto hidden max-w-[1400px] grid-cols-12 gap-6 px-6 lg:grid"
        >
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="border-r border-foreground/[0.06] first:border-l" />
          ))}
        </div>

        <div className="relative mx-auto grid max-w-[1400px] items-center gap-16 px-6 py-20 lg:grid-cols-[1.05fr_1fr] lg:py-28">
          {/* words */}
          <div>
            <div className="rise-in flex items-center gap-3.5">
              <span className="h-px w-8 bg-accent" />
              <span className="eyebrow text-accent">Maternal intelligence</span>
            </div>

            <h1 className="display mt-8 text-[clamp(3rem,7.5vw,7.25rem)]">
              <span className="mask">
                <span style={{ animationDelay: "0.14s" }}>Forty weeks.</span>
              </span>
              <span className="mask">
                <span style={{ animationDelay: "0.24s" }}>Nothing left</span>
              </span>
              <span className="mask">
                <span className="italic text-accent" style={{ animationDelay: "0.34s" }}>
                  to chance.
                </span>
              </span>
            </h1>

            <p
              className="rise-in mt-7 max-w-[28rem] text-[17px] leading-[1.68] text-muted-foreground"
              style={{ animationDelay: "0.52s" }}
            >
              Clinical guidance and Ayurvedic tradition, reconciled week by week. Every claim carries the
              source it came from — open it, read it, decide with your doctor.
            </p>

            <div
              className="rise-in mt-10 flex flex-wrap items-center gap-8"
              style={{ animationDelay: "0.62s" }}
            >
              <Link href="/signup">
                <Button size="lg">Start your week</Button>
              </Link>
              <Link
                href="/login"
                className="border-b border-foreground/30 pb-1 text-sm font-semibold transition-colors hover:border-accent hover:text-accent"
              >
                I already have an account
              </Link>
            </div>

            <dl
              className="rise-in mt-14 grid max-w-xl grid-cols-3 gap-6 border-t border-border pt-7"
              style={{ animationDelay: "0.74s" }}
            >
              <div>
                <dt className="sr-only">Weeks mapped</dt>
                <dd className="display text-[2.9rem]">40</dd>
                <p className="eyebrow-sm mt-2 text-muted-foreground">Weeks mapped</p>
              </div>
              <div>
                <dt className="sr-only">Sources cited</dt>
                <dd className="display text-[2.9rem]">[N]</dd>
                <p className="eyebrow-sm mt-2 text-muted-foreground">Sources cited</p>
              </div>
              <div>
                <dt className="sr-only">Mothers guided</dt>
                <dd className="display text-[2.9rem]">[N]</dd>
                <p className="eyebrow-sm mt-2 text-muted-foreground">Mothers guided</p>
              </div>
            </dl>
          </div>

          {/* the scene */}
          <div className="relative h-[34rem] [perspective:1900px] [perspective-origin:34%_42%] lg:h-[46rem]">
            <div className="animate-scene absolute inset-0 [transform-style:preserve-3d]">
              {/* back plane — the plate */}
              <div
                className="shadow-plate absolute left-0 top-4 hidden w-[17rem] overflow-hidden border border-border bg-card sm:block lg:top-8"
                style={{ transform: "translateZ(-150px)" }}
              >
                <Image
                  src="/plates/gestation.jpg"
                  alt="Watercolour study of pregnancy, conception through birth"
                  width={1400}
                  height={1400}
                  preload
                  className="h-[26rem] w-full object-cover"
                />
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-card via-card/85 to-transparent px-4 pb-3 pt-8">
                  <span className="eyebrow-sm text-muted-foreground">Plate I — Gestation</span>
                </div>
              </div>

              {/* mid plane — the product */}
              <div className="absolute left-0 top-16 flex w-full max-w-[27rem] flex-col border border-border bg-card p-7 shadow-[0_70px_110px_-46px_hsl(var(--ink)/0.48)] sm:left-28 lg:top-24">
                <div className="flex items-center justify-between border-b border-border pb-4">
                  <span className="eyebrow-sm text-muted-foreground">Today — 25 Sep</span>
                  <span className="eyebrow-sm flex items-center gap-2 text-accent">
                    <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent" />
                    Live
                  </span>
                </div>

                <div className="flex items-center gap-6 py-6">
                  <div className="relative h-[7.5rem] w-[7.5rem] shrink-0">
                    <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
                      <circle cx="60" cy="60" r="48" fill="none" stroke="hsl(var(--sage-200))" strokeWidth="3" />
                      <circle
                        cx="60"
                        cy="60"
                        r="48"
                        fill="none"
                        stroke="hsl(var(--accent))"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeDasharray={302}
                        strokeDashoffset={121}
                        className="animate-draw"
                        style={{ ["--dash" as string]: "302", animationDelay: "0.9s" }}
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="display text-[2.5rem]">24</span>
                      <span className="eyebrow-sm text-muted-foreground">Weeks</span>
                    </div>
                  </div>
                  <div>
                    <p className="eyebrow-sm text-accent">Second trimester</p>
                    <p className="display mt-2 text-[1.7rem] leading-[1.16]">
                      Hearing sharpens
                      <br />
                      this week.
                    </p>
                    <p className="mt-2.5 text-xs text-muted-foreground">112 days remaining</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-px border-y border-border bg-border">
                  {[
                    ["Iron", "27", "mg"],
                    ["Sleep", "7.2", "h"],
                    ["Steps", "4.1", "k"],
                  ].map(([label, value, unit], i) => (
                    <div key={label} className={`bg-card py-3.5 ${i > 0 ? "pl-3" : ""}`}>
                      <p className="eyebrow-sm text-muted-foreground">{label}</p>
                      <p className="display tabular mt-1 text-[1.55rem]">
                        {value}
                        <span className="text-xs text-muted-foreground">{unit}</span>
                      </p>
                    </div>
                  ))}
                </div>

                <div className="flex h-24 items-end gap-1.5 pt-5">
                  {[26, 44, 36, 62, 51, 74, 96].map((h, i) => (
                    <div
                      key={i}
                      style={{ height: `${h}%` }}
                      className={`flex-1 ${
                        i === 6 ? "bg-accent" : i === 5 ? "bg-sage-400" : i > 2 ? "bg-sage-200" : "bg-sage-100"
                      }`}
                    />
                  ))}
                </div>
                <div className="eyebrow-sm flex justify-between pt-2 text-muted-foreground">
                  <span>W18</span>
                  <span>W24</span>
                </div>
              </div>

              {/* front plane — fragments */}
              <div
                className="shadow-float absolute bottom-6 left-2 hidden border border-foreground/10 bg-sage-100 px-5 py-4 sm:block"
                style={{ ["--z" as string]: "112px", animation: "mv-drift 7s ease-in-out infinite" }}
              >
                <p className="eyebrow-sm text-accent">Next visit</p>
                <p className="display mt-1 text-[1.55rem]">Fri 3 Oct</p>
                <p className="mt-1 text-xs text-muted-foreground">Anomaly scan · Dr Nair</p>
              </div>

              <div
                className="absolute right-0 top-0 hidden items-center gap-2.5 bg-ink px-4 py-3 shadow-float md:flex"
                style={{ ["--z" as string]: "158px", animation: "mv-drift 6s ease-in-out infinite" }}
              >
                <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-blush-200" />
                <span className="text-[11px] font-bold tracking-[0.1em] text-cream-100">148 BPM</span>
                <span className="eyebrow-sm text-cream-100/60">Normal</span>
              </div>
            </div>
          </div>
        </div>

        {/* the ticker */}
        <div className="relative flex h-20 items-center overflow-hidden border-t border-border bg-cream-200/60">
          <Ticker />
        </div>
      </section>

      {/* ── pillars ───────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-[1400px] px-6 py-24">
        <div className="flex items-baseline gap-4 border-b border-foreground pb-3">
          <span className="eyebrow text-accent">What it does</span>
          <span className="eyebrow ml-auto text-muted-foreground">Four commitments</span>
        </div>

        {pillars.map((pillar) => (
          <article
            key={pillar.index}
            className="grid gap-4 border-b border-border py-9 transition-colors hover:bg-foreground/[0.02] md:grid-cols-[4rem_1fr_28rem] md:gap-8"
          >
            <span className="eyebrow-sm pt-2 text-muted-foreground">{pillar.index}</span>
            <h2 className="display text-[1.9rem] leading-[1.12]">{pillar.title}</h2>
            <p className="text-sm leading-[1.7] text-muted-foreground">{pillar.body}</p>
          </article>
        ))}
      </section>

      {/* ── close ─────────────────────────────────────────────── */}
      <section className="border-t border-border bg-sage-100">
        <div className="relative mx-auto grid max-w-[1400px] items-center gap-10 px-6 py-24 md:grid-cols-[1.2fr_1fr]">
          <div>
            <span className="eyebrow text-accent">Begin</span>
            <h2 className="display mt-6 max-w-2xl text-[clamp(2.25rem,4.5vw,3.5rem)] leading-[1.04]">
              Tell us your week. We will take it from there.
            </h2>
            <p className="mt-6 max-w-lg text-[15px] leading-[1.7] text-muted-foreground">
              Region, diet and stage in two minutes — then a dashboard that speaks to where you actually are.
            </p>
            <div className="mt-10">
              <Link href="/signup">
                <Button size="lg">Create your account</Button>
              </Link>
            </div>
          </div>

          <figure className="relative m-0 hidden md:block">
            <Image
              src="/plates/mother.jpg"
              alt="Illustration of a mother holding her unborn child"
              width={1400}
              height={819}
              className="shadow-plate h-[20rem] w-full object-cover"
            />
            <figcaption className="eyebrow-sm mt-3 flex justify-between text-muted-foreground">
              <span>Plate III — Second trimester</span>
              <span>Fig. 03</span>
            </figcaption>
          </figure>
        </div>
      </section>
    </main>
  );
}
