"use client";

import * as React from "react";
import { Loader2, MessageSquareText, SendHorizonal, Sparkles } from "lucide-react";

import type { ViewMessage } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";

interface ChatWorkspaceProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  history: ViewMessage[];
  loading: boolean;
  error: string | null;
  onSend: (question: string) => void;
  canSend: boolean;
  placeholder?: string;
  renderAssistantExtras?: (msg: ViewMessage) => React.ReactNode;
  children?: React.ReactNode;
}

export function ChatWorkspace({
  icon,
  title,
  description,
  history,
  loading,
  error,
  onSend,
  canSend,
  placeholder,
  renderAssistantExtras,
  children,
}: ChatWorkspaceProps) {
  const [draft, setDraft] = React.useState("");
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [history.length, loading]);

  const submit = () => {
    const question = draft.trim();
    if (!question || loading || !canSend) return;
    onSend(question);
    setDraft("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="border-b bg-background/95 px-6 py-4 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-foreground text-background">
            {icon}
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">{title}</h1>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
      </header>

      {children}

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {history.length === 0 && !loading && <EmptyState />}
          {history.map((msg, index) => (
            <MessageRow key={index} msg={msg} renderAssistantExtras={renderAssistantExtras} />
          ))}
          {loading && <ThinkingBubble />}
          {error && <ErrorBanner message={error} />}
        </div>
      </div>

      <div className="border-t bg-background px-4 py-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div className="flex items-end gap-2 rounded-xl border bg-card p-2 shadow-xs transition-colors focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20">
            <Textarea
              ref={textareaRef}
              rows={1}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder={placeholder ?? "Ask anything… (Enter to send)"}
              className="max-h-40 min-h-[44px] flex-1 resize-none border-0 bg-transparent p-1.5 shadow-none focus-visible:ring-0"
              disabled={loading}
            />
            <Button
              size="icon"
              onClick={submit}
              disabled={loading || !canSend || !draft.trim()}
              className="h-10 w-10 shrink-0 rounded-lg"
              aria-label="Send"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <SendHorizonal className="size-4" />}
            </Button>
          </div>
          <p className="mt-2 text-center text-[11px] text-muted-foreground">
            Responses run fully on this machine via Ollama — no data leaves your Mac.
          </p>
        </div>
      </div>
    </div>
  );
}
function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-secondary">
        <MessageSquareText className="size-5 text-muted-foreground" />
      </div>
      <p className="max-w-sm text-sm text-muted-foreground">
        Start a conversation below. The local model on this machine will respond instantly.
      </p>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-3">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-secondary">
          <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
        </div>
        <div className="flex flex-col gap-2 pt-1">
          <Skeleton className="h-3.5 w-52" />
          <Skeleton className="h-3.5 w-72" />
        </div>
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {message}
    </div>
  );
}

function MessageRow({
  msg,
  renderAssistantExtras,
}: {
  msg: ViewMessage;
  renderAssistantExtras?: (msg: ViewMessage) => React.ReactNode;
}) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%]">
        <div className="flex items-start gap-3">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-secondary">
            <Sparkles className="size-3.5 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="whitespace-pre-wrap rounded-2xl rounded-bl-sm border bg-card px-4 py-3 text-sm leading-relaxed text-card-foreground shadow-xs">
              {msg.content}
            </div>
            {renderAssistantExtras?.(msg)}
          </div>
        </div>
      </div>
    </div>
  );
}