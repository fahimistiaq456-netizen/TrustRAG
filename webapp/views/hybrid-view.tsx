"use client";

import * as React from "react";
import { Shuffle } from "lucide-react";

import type { RenderedMeta, ViewMessage } from "@/lib/types";
import { ChatWorkspace } from "@/components/chat-workspace";
import { RAGMeta } from "@/components/rag-meta";

interface HybridViewProps {
  history: ViewMessage[];
  loading: boolean;
  error: string | null;
  onSend: (question: string) => void;
  canSend: boolean;
}

export function HybridView({ history, loading, error, onSend, canSend }: HybridViewProps) {
  const renderExtras = (msg: ViewMessage): React.ReactNode => {
    const meta = msg.meta as RenderedMeta | undefined;
    return meta && meta.mode ? <RAGMeta meta={meta} /> : null;
  };

  return (
    <ChatWorkspace
      icon={<Shuffle className="size-4" />}
      title="Hybrid"
      description="Source first, local model as fallback — verified RAG when the source matches."
      history={history}
      loading={loading}
      error={error}
      onSend={onSend}
      canSend={canSend}
      renderAssistantExtras={renderExtras}
      placeholder="Ask anything — source question or general conversation…"
    />
  );
}