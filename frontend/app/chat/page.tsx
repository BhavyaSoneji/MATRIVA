"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { ChatResponse, ChatHistoryResponse, Citation, SourceResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner, LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { EvidenceBadge, SafetyBadge } from "@/components/evidence-badge";
import { ThumbsUp, ThumbsDown, Send, AlertTriangle } from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  sources?: SourceResponse[];
  safetyStatus?: string;
  feedbackGiven?: "up" | "down";
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

function ChatContent() {
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [input, setInput] = React.useState("");
  const [conversationId, setConversationId] = React.useState<string | undefined>(undefined);
  const [sending, setSending] = React.useState(false);
  const [historyLoading, setHistoryLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  // GET /chat/history requires a conversation_id -- there is no "list my
  // conversations" endpoint, so history can only be resumed for a
  // conversation this browser has already started (persisted below).
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
        const loaded: ChatMessage[] = res.messages.map((m, idx) => ({
          id: String((m as { id?: string }).id ?? idx),
          role: (m as { role?: string }).role === "assistant" ? "assistant" : "user",
          text: String((m as { content?: string }).content ?? ""),
        }));
        setMessages(loaded);
      })
      .catch(() => {
        // Stored conversation is gone/inaccessible -- start fresh rather than looping on it.
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
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || sending) return;
    setError(null);
    const userMsg: ChatMessage = { id: `u-${crypto.randomUUID()}`, role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    try {
      const res = await api.post<ChatResponse>("/chat", {
        message: text,
        conversation_id: conversationId,
      });
      setConversationId(res.conversation_id);
      localStorage.setItem(CONVERSATION_STORAGE_KEY, res.conversation_id);
      const assistantMsg: ChatMessage = {
        id: res.message_id,
        role: "assistant",
        text: res.answer,
        citations: res.citations,
        sources: res.sources,
        safetyStatus: res.safety_status,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send your message. Please try again.");
    } finally {
      setSending(false);
    }
  };

  const submitFeedback = async (messageId: string, rating: 1 | 5, direction: "up" | "down") => {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedbackGiven: direction } : m)));
    try {
      await api.post("/feedback", { message_id: messageId, rating });
    } catch {
      // feedback failure shouldn't disrupt the chat UI
    }
  };

  return (
    <main className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 py-6">
      <h1 className="mb-4 text-xl font-semibold text-foreground">Chat with MATRIVA</h1>

      <div className="flex-1 overflow-y-auto border border-border bg-card p-4">
        {historyLoading && <LoadingState label="Loading conversation..." />}
        {!historyLoading && messages.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Ask a question about nutrition, lifestyle, or your pregnancy stage to get started.
          </p>
        )}
        <div className="flex flex-col gap-4">
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] ${m.role === "user" ? "" : "w-full"}`}>
                {m.role === "assistant" && m.safetyStatus && URGENT_STATUSES.has(m.safetyStatus) && (
                  <Alert variant="destructive" className="mb-2">
                    <AlertTriangle className="inline h-4 w-4" />
                    <AlertTitle>Please seek medical attention</AlertTitle>
                    <AlertDescription>
                      This response indicates a concern that may need urgent care. Contact your healthcare provider
                      immediately.
                    </AlertDescription>
                  </Alert>
                )}
                <div
                  className={`border px-4 py-2.5 text-sm ${
                    m.role === "user"
                      ? "border-transparent bg-primary text-primary-foreground"
                      : "border-border bg-muted text-foreground"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  {m.safetyStatus && m.role === "assistant" && (
                    <div className="mt-2">
                      <SafetyBadge status={m.safetyStatus} />
                    </div>
                  )}
                </div>
                {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {m.sources.map((s) => (
                      <Card key={s.id} className="border-border/80">
                        <CardContent className="flex flex-col gap-1 p-3">
                          <p className="text-xs font-medium text-foreground">{s.title || s.name}</p>
                          <div className="flex items-center gap-1.5">
                            <EvidenceBadge level={s.evidence_level} />
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
                {m.role === "assistant" && (
                  <div className="mt-1.5 flex gap-2">
                    <button
                      aria-label="Good response"
                      onClick={() => submitFeedback(m.id, 5, "up")}
                      className={`rounded p-1 hover:bg-muted ${m.feedbackGiven === "up" ? "text-primary" : "text-muted-foreground"}`}
                    >
                      <ThumbsUp className="h-4 w-4" />
                    </button>
                    <button
                      aria-label="Bad response"
                      onClick={() => submitFeedback(m.id, 1, "down")}
                      className={`rounded p-1 hover:bg-muted ${m.feedbackGiven === "down" ? "text-destructive" : "text-muted-foreground"}`}
                    >
                      <ThumbsDown className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 border border-border bg-muted px-4 py-2.5 text-sm text-muted-foreground">
                <Spinner className="h-4 w-4" /> Thinking...
              </div>
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>

      {error && (
        <Alert variant="destructive" className="mt-3">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => sendMessage(q)}
            disabled={sending}
            className="border border-border bg-background px-3 py-1.5 text-xs text-foreground/80 hover:bg-muted disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage(input);
        }}
      >
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask MATRIVA a question..."
          className="min-h-[48px] flex-1 resize-none"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage(input);
            }
          }}
        />
        <Button type="submit" disabled={sending || !input.trim()} size="icon">
          <Send className="h-4 w-4" />
        </Button>
      </form>
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
