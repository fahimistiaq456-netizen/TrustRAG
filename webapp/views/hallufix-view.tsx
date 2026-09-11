"use client";

import * as React from "react";
import { ShieldCheck } from "lucide-react";

import type { RenderedMeta, ViewMessage } from "@/lib/types";
import { ChatWorkspace } from "@/components/chat-workspace";
import { RAGMeta } from "@/components/rag-meta";

interface HallufixViewProps {
  history: ViewMessage[];
  loading: boolean;
  error: string | null;
  onSend: (question: string) => void;
  canSend: boolean;
}

export function HallufixView({ history, loading, error, onSend, canSend }: HallufixViewProps) {
  const renderExtras = (msg: ViewMessage): React.ReactNode => {
    const meta = msg.meta as RenderedMeta | undefined;
    return meta && meta.mode ? <RAGMeta meta={meta} /> : null;
  };

  return (
    <ChatWorkspace
      icon={<ShieldCheck className="size-4" />}
      title="TrustRAG"
      description="Source-first retrieval: abstain-gate, grounded generation, claim verification, and citations."
      history={history}
      loading={loading}
      error={error}
      onSend={onSend}
      canSend={canSend}
      renderAssistantExtras={renderExtras}
      placeholder="Ask a question answerable from your source library…"
    />
  );
}