import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ShieldCheck, Sprout, MessagesSquare, HeartPulse } from "lucide-react";
import { PregnancyVisualization } from "@/components/pregnancy-visualization";

const features = [
  {
    icon: ShieldCheck,
    title: "Safety-first guidance",
    description:
      "Every answer is checked against safety rules. Anything urgent is flagged clearly, so you know when to see a doctor.",
  },
  {
    icon: HeartPulse,
    title: "Grounded in real evidence",
    description:
      "Recommendations cite modern medical sources with transparent evidence levels — supported, preliminary, or uncertain.",
  },
  {
    icon: Sprout,
    title: "Traditional & Ayurvedic knowledge",
    description:
      "Explore traditional practices alongside modern medicine, always clearly labeled as traditional rather than clinically proven.",
  },
  {
    icon: MessagesSquare,
    title: "Ask anything, anytime",
    description:
      "Chat with MATRIVA about nutrition, lifestyle, and stage-specific guidance, with sources for every answer.",
  },
];

export default function Home() {
  return (
    <main className="flex flex-col">
      <section className="bg-wellness-gradient border-b border-border">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 md:grid-cols-2 md:items-center md:py-24">
          <div className="flex flex-col items-start gap-6 text-left">
            <span className="border border-primary/30 bg-sky-50 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
              Pregnancy guidance you can trust
            </span>
            <h1 className="max-w-xl text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
              Calm, evidence-based guidance for every stage of your pregnancy
            </h1>
            <p className="max-w-xl text-lg text-muted-foreground">
              MATRIVA blends modern medical evidence with traditional and Ayurvedic knowledge to help you make
              informed, safe choices — with clear sourcing and a safety net that never lets a serious concern slip
              by.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Link href="/signup">
                <Button size="lg">Get started free</Button>
              </Link>
              <Link href="/login">
                <Button size="lg" variant="outline">
                  Log in
                </Button>
              </Link>
            </div>
          </div>
          <div className="flex justify-center md:justify-end">
            <PregnancyVisualization trimester={3} currentWeek={34} variant="hero" />
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-6xl px-4 py-16">
        <div className="grid gap-6 sm:grid-cols-2">
          {features.map((feature) => (
            <Card key={feature.title}>
              <CardHeader>
                <feature.icon className="mb-2 h-8 w-8 text-primary" />
                <CardTitle>{feature.title}</CardTitle>
                <CardDescription>{feature.description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-sky-50">
        <div className="mx-auto max-w-6xl px-4 py-16 text-center">
          <CardContent className="flex flex-col items-center gap-4 p-0">
            <h2 className="text-2xl font-semibold text-foreground">Ready for personalized guidance?</h2>
            <p className="max-w-xl text-muted-foreground">
              Create your free account, tell us about your pregnancy, and get a dashboard tailored to your stage,
              region, and preferences.
            </p>
            <Link href="/signup">
              <Button size="lg">Create your account</Button>
            </Link>
          </CardContent>
        </div>
      </section>
    </main>
  );
}
