"use client";

import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Cpu,
  Server,
  ShieldCheck,
  Shuffle,
  XCircle,
} from "lucide-react";

import type { Health, ViewMessage } from "@/lib/types";
import type { ViewKey } from "@/components/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface OverviewViewProps {
  health: Health | null;
  healthLoading: boolean;
  normalHistory: ViewMessage[];
  hallufixHistory: ViewMessage[];
  hybridHistory: ViewMessage[];
  onNavigate: (view: ViewKey) => void;
}

const MODES: { key: ViewKey; title: string; desc: string; icon: React.ReactNode }[] = [
  {
    key: "normal",
    title: "Normal chat",
    desc: "Natural conversation with the local model. No retrieval, no citations.",
    icon: <Bot className="size-4" />,
  },
  {
    key: "hallufix",
    title: "TrustRAG",
    desc: "Source-first RAG: retrieve, abstain-gate, generate, verify, cite.",
    icon: <ShieldCheck className="size-4" />,
  },
  {
    key: "hybrid",
    title: "Hybrid",
    desc: "Source answers when indexed; otherwise the local model responds.",
    icon: <Shuffle className="size-4" />,
  },
];

function lastQuestion(history: ViewMessage[]): string | null {
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].role === "user") return history[i].content;
  }
  return null;
}
export function OverviewView({
  health,
  healthLoading,
  normalHistory,
  hallufixHistory,
  hybridHistory,
  onNavigate,
}: OverviewViewProps) {
  const ollamaOk = health?.ollama_running ?? false;
  const recent: { title: string; question: string | null }[] = [
    { title: "Normal", question: lastQuestion(normalHistory) },
    { title: "TrustRAG", question: lastQuestion(hallufixHistory) },
    { title: "Hybrid", question: lastQuestion(hybridHistory) },
  ];

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <header className="border-b bg-background/95 px-4 py-3 sm:px-6 sm:py-4 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-foreground text-background">
            <Bot className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-semibold tracking-tight truncate">TrustRAG Local Lab</h1>
            <p className="text-xs sm:text-sm text-muted-foreground truncate">
              Three answer modes, one model — compare verified RAG side by side.
            </p>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-4xl flex-1 space-y-4 sm:space-y-6 px-4 py-4 sm:px-6 sm:py-6">
        <Card>
          <CardContent className="py-4 sm:py-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-secondary">
                  <Server className="size-4 text-muted-foreground" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {healthLoading ? (
                      <Badge variant="outline">Checking…</Badge>
                    ) : ollamaOk ? (
                      <Badge>
                        <CheckCircle2 className="size-3" /> Backend online
                      </Badge>
                    ) : (
                      <Badge variant="destructive">
                        <XCircle className="size-3" /> Offline
                      </Badge>
                    )}
                    {health?.selected_model && <Badge variant="outline">{health.selected_model}</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {ollamaOk
                      ? "LLM inference engine is online and ready."
                      : "Connecting to FastAPI backend..."}
                  </p>
                </div>
              </div>
              <Button variant="outline" className="w-full sm:w-auto" onClick={() => onNavigate("normal")}>
                Start chatting <ArrowRight className="size-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {MODES.map((mode) => {
            const history =
              mode.key === "normal"
                ? normalHistory
                : mode.key === "hallufix"
                  ? hallufixHistory
                  : hybridHistory;
            return (
              <Card key={mode.key} className="gap-3">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <span className="flex size-7 items-center justify-center rounded-lg bg-secondary">
                      {mode.icon}
                    </span>
                    {mode.title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-3">
                  <p className="text-xs leading-relaxed text-muted-foreground">{mode.desc}</p>
                  <Separator />
                  {history.length > 0 ? (
                    <p className="line-clamp-2 min-h-[2rem] text-xs text-muted-foreground">
                      Last: “{lastQuestion(history)}”
                    </p>
                  ) : (
                    <p className="min-h-[2rem] text-xs text-muted-foreground">No messages yet.</p>
                  )}
                  <Button variant="outline" size="sm" className="w-full" onClick={() => onNavigate(mode.key)}>
                    Open {mode.title}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Recent questions per mode</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {recent.map((r) => (
              <div key={r.title} className="flex items-center gap-3 text-sm">
                <Badge variant="outline" className="w-16 justify-center font-mono">
                  {r.title}
                </Badge>
                <span className="truncate text-muted-foreground">{r.question ?? "—"}</span>
              </div>
            ))}
            <Separator className="pt-2" />
            <div className="flex items-center gap-2 pt-2 text-xs text-muted-foreground">
              <Cpu className="size-3.5" />
              Everything runs locally: FAISS embedding + Ollama inference on this machine.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}