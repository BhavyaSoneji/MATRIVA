"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, streamChat } from "@/lib/api";
import type {
  ChatHistoryResponse,
  Citation,
  SourceResponse,
  RecommendationResponse,
} from "@/lib/types";
import { ChatAnswer } from "@/components/chat-answer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge, SafetyBadge } from "@/components/evidence-badge";
import {
  ThumbsUp,
  ThumbsDown,
  ArrowRight,
  TriangleAlert,
  Square,
  RotateCcw,
  Copy,
  Check,
  Globe,
  ChevronDown,
  Plus,
} from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt?: string;
  citations?: Citation[];
  sources?: SourceResponse[];
  safetyStatus?: string;
  evidence?: Record<string, unknown>;
  recommendations?: RecommendationResponse[];
  feedbackGiven?: "up" | "down";
  streaming?: boolean;
  stopped?: boolean;
  failed?: boolean;
}

const SUGGESTED_QUESTIONS = [
  "What foods should I avoid in my first trimester?",
  "Is it safe to do yoga during pregnancy?",
  "What does Ayurveda say about diet during pregnancy?",
  "When is my next prenatal checkup?",
  "What are signs I should call my doctor right away?",
];

const URGENT_STATUSES = new Set(["high_risk", "urgent_escalation"]);
const CONVERSATION_STORAGE_KEY = "matriva.conversationId";
const MAX_MESSAGE_CHARS = 4000; // mirrors backend Settings.max_message_chars

/** Builds minimal SourceResponse stand-ins from citations so a message
 * reloaded from /chat/history (which carries citations but not full source
 * records) can still render evidence badges and titles consistently. */
function sourcesFromCitations(citations: Citation[]): SourceResponse[] {
  return citations.map((c) => ({
    id: c.source_id,
    name: c.source_name,
    title: c.source_name,
    source_type: c.source_type ?? "internal",
    authority: null,
    jurisdiction: null,
    topic: null,
    url: c.url ?? null,
    version: null,
    publication_date: null,
    review_status: "approved",
    evidence_level: c.evidence_level,
    evidence_label: null,
    page_or_section: c.locator,
    extra_metadata: {},
  }));
}

function timeLabel(iso?: string) {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      aria-label="Copy answer"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {
          // clipboard permission denied -- silently ignore, button just won't confirm
        }
      }}
      className="flex h-9 w-9 items-center justify-center border border-border text-muted-foreground transition-colors hover:text-accent"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function EvidencePanel({ evidence, citations }: { evidence: Record<string, unknown>; citations: Citation[] }) {
  const retrievalCount = evidence.retrieval_count;
  const retrievalMs = Number(evidence.retrieval_latency_ms ?? 0);
  const generationMs = Number(evidence.generation_latency_ms ?? 0);
  const webSearchUsed = Boolean(evidence.web_search_used);
  const validation = evidence.citation_validation;
  const webCitations = citations.filter((c) => c.source_type === "external_web");

  return (
    <details className="group mt-1">
      <summary className="eyebrow-sm flex w-fit cursor-pointer list-none items-center gap-1.5 text-muted-foreground transition-colors hover:text-accent">
        <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" aria-hidden="true" />
        How this was answered
      </summary>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 border-l-2 border-border pl-4 text-[11.5px] text-muted-foreground sm:grid-cols-4">
        <div>
          <dt className="eyebrow-sm">Passages checked</dt>
          <dd className="tabular mt-1 text-foreground">{String(retrievalCount ?? "—")}</dd>
        </div>
        <div>
          <dt className="eyebrow-sm">Retrieval</dt>
          <dd className="tabular mt-1 text-foreground">{retrievalMs.toFixed(1)} ms</dd>
        </div>
        <div>
          <dt className="eyebrow-sm">Generation</dt>
          <dd className="tabular mt-1 text-foreground">{generationMs.toFixed(1)} ms</dd>
        </div>
        <div>
          <dt className="eyebrow-sm">Citations</dt>
          <dd className="mt-1 capitalize text-foreground">{String(validation ?? "—")}</dd>
        </div>
      </dl>
      {webSearchUsed && (
        <p className="mt-3 flex items-center gap-1.5 pl-4 text-[11.5px] text-accent">
          <Globe className="h-3 w-3" aria-hidden="true" />
          Included {webCitations.length || "live"} web result{webCitations.length === 1 ? "" : "s"}, alongside
          reviewed documents
        </p>
      )}
    </details>
  );
}

function RelatedRecommendations({ items }: { items: RecommendationResponse[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2 flex flex-col gap-2 border-t border-border pt-4">
      <p className="eyebrow-sm text-muted-foreground">Related to your stage</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {items.slice(0, 2).map((r) => (
          <div key={r.id} className="border border-border p-3.5">
            <div className="flex items-start justify-between gap-2">
              <p className="eyebrow-sm text-accent">{r.domain}</p>
              <EvidenceBadge level={r.evidence_level} />
            </div>
            <p className="display mt-1.5 text-[15px] leading-[1.25]">{r.title}</p>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">{r.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChatContent() {
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [input, setInput] = React.useState("");
  const [conversationId, setConversationId] = React.useState<string | undefined>(undefined);
  const [sending, setSending] = React.useState(false);
  const [historyLoading, setHistoryLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [pinnedToBottom, setPinnedToBottom] = React.useState(true);

  const scrollRef = React.useRef<HTMLDivElement>(null);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const abortRef = React.useRef<AbortController | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const storedId = typeof window !== "undefined" ? localStorage.getItem(CONVERSATION_STORAGE_KEY) : null;
    if (!storedId) {
      setHistoryLoading(false);
      return;
    }
    api
      .get<ChatHistoryResponse>(`/chat/history?conversation_id=${encodeURIComponent(storedId)}`)
      .then((res) => {
        if (cancelled) return;
        setConversationId(res.conversation_id);
        const loaded: ChatMessage[] = res.messages.map((m, idx) => {
          const citations = ((m as { citations?: Citation[] }).citations ?? []) as Citation[];
          return {
            id: String((m as { id?: string }).id ?? idx),
            role: (m as { role?: string }).role === "assistant" ? "assistant" : "user",
            text: String((m as { content?: string }).content ?? ""),
            createdAt: (m as { created_at?: string }).created_at,
            safetyStatus: (m as { safety_status?: string }).safety_status ?? undefined,
            citations,
            sources: citations.length > 0 ? sourcesFromCitations(citations) : undefined,
          };
        });
        setMessages(loaded);
      })
      .catch(() => {
        localStorage.removeItem(CONVERSATION_STORAGE_KEY);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (pinnedToBottom) scrollRef.current?.scrollIntoView({ block: "end" });
  }, [messages, pinnedToBottom]);

  // auto-grow the composer up to a sane cap
  React.useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  React.useEffect(() => () => abortRef.current?.abort(), []);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setPinnedToBottom(distanceFromBottom < 96);
  };

  const patchMessage = (id: string, patch: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...(typeof patch === "function" ? patch(m) : patch) } : m))
    );
  };

  const sendMessage = async (text: string, opts?: { skipUserBubble?: boolean }) => {
    const trimmed = text.trim();
    if (!trimmed || sending || trimmed.length > MAX_MESSAGE_CHARS) return;
    setError(null);

    if (!opts?.skipUserBubble) {
      const userMsg: ChatMessage = {
        id: `u-${crypto.randomUUID()}`,
        role: "user",
        text: trimmed,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
    }
    setInput("");
    setPinnedToBottom(true);
    setSending(true);

    const assistantId = `a-${crypto.randomUUID()}`;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", text: "", streaming: true, createdAt: new Date().toISOString() },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    await streamChat(
      { message: trimmed, conversation_id: conversationId },
      {
        onDelta: (delta) => {
          patchMessage(assistantId, (m) => ({ text: m.text + delta }));
        },
        onFinal: (data) => {
          patchMessage(assistantId, {
            text: data.answer,
            safetyStatus: data.safety_status,
            citations: data.citations,
          });
        },
        onDone: (data) => {
          setConversationId(data.conversation_id);
          localStorage.setItem(CONVERSATION_STORAGE_KEY, data.conversation_id);
          patchMessage(assistantId, {
            id: data.message_id,
            sources: data.sources,
            evidence: data.evidence,
            recommendations: data.recommendations,
            streaming: false,
          });
        },
        onError: (message) => {
          patchMessage(assistantId, { text: message, streaming: false, failed: true });
        },
      },
      controller.signal
    );

    setSending(false);
    abortRef.current = null;
  };

  const stopGenerating = () => {
    abortRef.current?.abort();
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false, stopped: true } : m))
    );
    setSending(false);
  };

  const regenerate = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser || sending) return;
    setMessages((prev) => {
      const lastAssistantIdx = prev.map((m) => m.role).lastIndexOf("assistant");
      return lastAssistantIdx === -1 ? prev : prev.slice(0, lastAssistantIdx);
    });
    void sendMessage(lastUser.text, { skipUserBubble: true });
  };

  const newThread = () => {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(undefined);
    setInput("");
    setError(null);
    setSending(false);
    localStorage.removeItem(CONVERSATION_STORAGE_KEY);
    textareaRef.current?.focus();
  };

  const submitFeedback = async (messageId: string, rating: 1 | 5, direction: "up" | "down") => {
    patchMessage(messageId, { feedbackGiven: direction });
    try {
      await api.post("/feedback", { message_id: messageId, rating });
    } catch {
      // feedback failure shouldn't disrupt the chat UI
    }
  };

  const charCount = input.length;
  const nearLimit = charCount > MAX_MESSAGE_CHARS * 0.85;
  const overLimit = charCount > MAX_MESSAGE_CHARS;
  const canRegenerate = !sending && messages.some((m) => m.role === "assistant");

  return (
    <main className="mx-auto flex h-[calc(100vh-4rem)] max-w-[880px] flex-col px-6">
      <div className="flex shrink-0 items-baseline justify-between border-b border-border py-6">
        <div>
          <h1 className="display text-2xl leading-none">The companion</h1>
          <p className="eyebrow-sm mt-2 text-muted-foreground">Answers cite the guideline they came from.</p>
        </div>
        <div className="flex items-center gap-5">
          <span className="eyebrow-sm text-muted-foreground">{messages.length} messages</span>
          <button
            type="button"
            onClick={newThread}
            disabled={messages.length === 0 && !conversationId}
            className="eyebrow-sm flex items-center gap-1.5 border border-border px-3 py-2 text-foreground transition-colors hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-40"
          >
            <Plus className="h-3 w-3" aria-hidden="true" />
            New thread
          </button>
        </div>
      </div>

      <div className="relative flex-1 overflow-hidden">
        <div onScroll={handleScroll} className="h-full overflow-y-auto py-8">
          {historyLoading && (
            <div className="flex flex-col gap-3 py-8">
              {[0, 1].map((i) => (
                <div key={i} className="h-16 animate-pulse bg-sage-100/60" style={{ animationDelay: `${i * 120}ms` }} />
              ))}
            </div>
          )}

          {!historyLoading && messages.length === 0 && (
            <div className="py-10 text-center">
              <p className="text-sm text-muted-foreground">
                Ask a question about nutrition, lifestyle, or your pregnancy stage to get started.
              </p>
              <p className="eyebrow-sm mt-3 text-muted-foreground/70">
                Every answer traces back to a reviewed source, or says plainly when it can&apos;t.
              </p>
            </div>
          )}

          <div className="flex flex-col gap-10">
            {messages.map((m) => (
              <div key={m.id}>
                {m.role === "user" ? (
                  <div className="ml-auto max-w-[70%] border-r-2 border-accent py-1 pr-4 text-right">
                    <p className="eyebrow-sm mb-2 text-muted-foreground">You · {timeLabel(m.createdAt)}</p>
                    <p className="text-[16px] leading-[1.6]">{m.text}</p>
                  </div>
                ) : (
                  <div className="flex gap-4">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-accent/45 font-display text-sm text-accent">
                      M
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="eyebrow-sm mb-2.5 text-muted-foreground">
                        MATRIVA · {timeLabel(m.createdAt)}
                        {m.stopped && <span className="ml-2 text-accent">· stopped</span>}
                      </p>

                      {m.safetyStatus && URGENT_STATUSES.has(m.safetyStatus) && (
                        <div className="mb-4 flex items-start gap-3 border-l-2 border-blush-500 bg-blush-100 px-4 py-3">
                          <TriangleAlert className="h-4 w-4 shrink-0 text-blush-500" aria-hidden="true" />
                          <p className="text-sm text-foreground/85">
                            This response indicates a concern that may need urgent care. Contact your
                            healthcare provider immediately.
                          </p>
                        </div>
                      )}

                      {m.text ? (
                        <ChatAnswer text={m.text} sources={m.sources ?? []} />
                      ) : m.streaming ? (
                        <span className="inline-flex items-center gap-1.5 text-muted-foreground" aria-live="polite">
                          <span className="sr-only">MATRIVA is checking sources…</span>
                          {[0, 1, 2].map((i) => (
                            <span
                              key={i}
                              className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent"
                              style={{ animationDelay: `${i * 0.16}s` }}
                            />
                          ))}
                        </span>
                      ) : null}

                      {m.streaming && m.text && (
                        <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse-soft bg-accent align-middle" />
                      )}

                      {m.safetyStatus && !m.streaming && <div className="mt-3.5">{<SafetyBadge status={m.safetyStatus} />}</div>}

                      {m.citations && m.citations.length > 0 && (
                        <div className="mt-5 flex flex-col gap-2 border-t border-border pt-4">
                          {m.citations.map((c, i) => (
                            <div key={i} className="flex items-baseline gap-3.5 text-muted-foreground">
                              <span className="eyebrow-sm shrink-0 text-accent">{i + 1}</span>
                              {c.source_type === "external_web" ? (
                                <Globe className="h-3 w-3 shrink-0" aria-hidden="true" />
                              ) : null}
                              <span className="flex-1 text-xs leading-relaxed">
                                {c.url ? (
                                  <a
                                    href={c.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-foreground underline decoration-border underline-offset-2 hover:text-accent"
                                  >
                                    {c.source_name}
                                  </a>
                                ) : (
                                  <span className="text-foreground">{c.source_name}</span>
                                )}
                                {c.locator && <span className="text-muted-foreground"> · {c.locator}</span>}
                              </span>
                              <EvidenceBadge level={c.evidence_level} />
                            </div>
                          ))}
                        </div>
                      )}

                      {m.recommendations && <RelatedRecommendations items={m.recommendations} />}

                      {m.evidence && Object.keys(m.evidence).length > 0 && (
                        <EvidencePanel evidence={m.evidence} citations={m.citations ?? []} />
                      )}

                      {!m.streaming && m.text && (
                        <div className="mt-3.5 flex items-center gap-2.5">
                          <span className="mr-1 text-[11px] text-muted-foreground">Was this useful?</span>
                          <button
                            type="button"
                            aria-label="Good response"
                            onClick={() => submitFeedback(m.id, 5, "up")}
                            className={`flex h-9 w-9 items-center justify-center border border-border transition-colors ${
                              m.feedbackGiven === "up" ? "border-accent text-accent" : "text-muted-foreground hover:text-accent"
                            }`}
                          >
                            <ThumbsUp className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            aria-label="Bad response"
                            onClick={() => submitFeedback(m.id, 1, "down")}
                            className={`flex h-9 w-9 items-center justify-center border border-border transition-colors ${
                              m.feedbackGiven === "down" ? "border-blush-500 text-blush-500" : "text-muted-foreground hover:text-blush-500"
                            }`}
                          >
                            <ThumbsDown className="h-3.5 w-3.5" />
                          </button>
                          <CopyButton text={m.text} />
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div ref={scrollRef} />
        </div>

        {!pinnedToBottom && messages.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setPinnedToBottom(true);
              scrollRef.current?.scrollIntoView({ block: "end" });
            }}
            className="eyebrow-sm absolute bottom-3 left-1/2 -translate-x-1/2 border border-border bg-card px-4 py-2 text-foreground shadow-card transition-colors hover:border-accent hover:text-accent"
          >
            ↓ Jump to latest
          </button>
        )}
      </div>

      <div className="shrink-0 border-t border-border py-5">
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="mb-4 flex flex-wrap items-center gap-2.5">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => sendMessage(q)}
              disabled={sending}
              className="border border-border px-3.5 py-2 text-[11.5px] text-muted-foreground transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
            >
              {q}
            </button>
          ))}
          {canRegenerate && (
            <button
              type="button"
              onClick={regenerate}
              className="eyebrow-sm ml-auto flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-accent"
            >
              <RotateCcw className="h-3 w-3" aria-hidden="true" />
              Regenerate
            </button>
          )}
        </div>

        <form
          className="flex items-end gap-3 border border-border bg-card"
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything — answers come with their sources"
            rows={1}
            className="max-h-[200px] min-h-[62px] flex-1 resize-none border-0 bg-transparent px-4 py-[19px] text-base text-foreground outline-none placeholder:text-muted-foreground/70"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
            }}
          />
          {sending ? (
            <button
              type="button"
              onClick={stopGenerating}
              aria-label="Stop generating"
              className="flex h-[62px] w-[62px] shrink-0 items-center justify-center bg-blush-500 text-cream-100"
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              aria-label="Send"
              disabled={!input.trim() || overLimit}
              className="flex h-[62px] w-[62px] shrink-0 items-center justify-center bg-primary text-primary-foreground transition-opacity disabled:opacity-40"
            >
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </form>
        <div className="mt-2.5 flex items-center justify-between">
          <p className="text-[10.5px] text-muted-foreground">
            MATRIVA is guidance, not a diagnosis. Urgent symptoms go to your provider.
          </p>
          {nearLimit && (
            <span className={`tabular text-[10.5px] ${overLimit ? "text-blush-500" : "text-muted-foreground"}`}>
              {charCount.toLocaleString()} / {MAX_MESSAGE_CHARS.toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </main>
  );
}

export default function ChatPage() {
  return (
    <RequireAuth>
      <ChatContent />
    </RequireAuth>
  );
}
