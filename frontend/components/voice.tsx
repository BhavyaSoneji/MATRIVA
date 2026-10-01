"use client";

import * as React from "react";
import { Mic, MicOff, Volume2, VolumeX } from "lucide-react";
import { speechLocale, type Lang } from "@/lib/language";

// The Web Speech API is not in TypeScript's DOM lib everywhere, so describe just what we use.
interface RecognitionResultEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: RecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** Microphone button: dictates into the composer. Renders nothing where the browser has no speech
 * recognition (e.g. Firefox), so it never shows a control that cannot work. */
export function MicButton({ lang, onText, disabled }: { lang: Lang; onText: (text: string) => void; disabled?: boolean }) {
  const [supported, setSupported] = React.useState(false);
  const [listening, setListening] = React.useState(false);
  const recRef = React.useRef<Recognition | null>(null);

  React.useEffect(() => {
    setSupported(recognitionCtor() !== null);
    return () => recRef.current?.stop();
  }, []);

  if (!supported) return null;

  const toggle = () => {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = speechLocale(lang);
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e) => {
      const last = e.results[e.results.length - 1];
      const text = last?.[0]?.transcript?.trim();
      if (text) onText(text);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  };

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      aria-pressed={listening}
      aria-label={listening ? "Stop dictation" : "Speak your question"}
      className={`flex h-[62px] w-12 shrink-0 items-center justify-center transition-colors disabled:opacity-40 ${
        listening ? "text-blush-500" : "text-muted-foreground hover:text-accent"
      }`}
    >
      {listening ? <MicOff className="h-4 w-4 animate-pulse" /> : <Mic className="h-4 w-4" />}
    </button>
  );
}

/** Read an answer aloud. Hidden when speech synthesis is unavailable. */
export function SpeakButton({ text, lang }: { text: string; lang: Lang }) {
  const [supported, setSupported] = React.useState(false);
  const [speaking, setSpeaking] = React.useState(false);

  React.useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  if (!supported) return null;

  const toggle = () => {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    // Strip the "[source_id=...]" markers and markdown bullets so the voice reads clean prose.
    const clean = text.replace(/\[source_id=[^\]]*\]/g, "").replace(/^[-*]\s+/gm, "").replace(/[*_#`]/g, "");
    const utter = new SpeechSynthesisUtterance(clean);
    utter.lang = speechLocale(lang);
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    synth.cancel();
    setSpeaking(true);
    synth.speak(utter);
  };

  return (
    <button
      type="button"
      aria-label={speaking ? "Stop reading aloud" : "Read answer aloud"}
      onClick={toggle}
      className="flex h-9 w-9 items-center justify-center border border-border text-muted-foreground transition-colors hover:text-accent"
    >
      {speaking ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
    </button>
  );
}
