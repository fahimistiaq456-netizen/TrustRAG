"use client";

import { Bot } from "lucide-react";

import type { ViewMessage } from "@/lib/types";
import { ChatWorkspace } from "@/components/chat-workspace";

interface NormalViewProps {
  history: ViewMessage[];
  loading: boolean;
  error: string | null;
  onSend: (question: string) => void;
  canSend: boolean;
}

export function NormalView({ history, loading, error, onSend, canSend }: NormalViewProps) {
  return (
    <ChatWorkspace
      icon={<Bot className="size-4" />}
      title="Normal chat"
      description="The local model talks naturally, without retrieval or citations."
      history={history}
      loading={loading}
      error={error}
      onSend={onSend}
      canSend={canSend}
      placeholder="Talk to the local model… (Enter to send)"
    />
  );
}