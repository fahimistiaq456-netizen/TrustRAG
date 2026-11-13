"use client";

import * as React from "react";
import { Menu } from "lucide-react";

import { Sidebar, type ViewKey } from "@/components/sidebar";
import { getHealth, hallufixAsk, hybridChat, normalChat } from "@/lib/api";
import type { ChatMessage, Health, RenderedMeta, ViewMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { OverviewView } from "@/views/overview-view";
import { NormalView } from "@/views/normal-view";
import { HallufixView } from "@/views/hallufix-view";
import { HybridView } from "@/views/hybrid-view";
import { SourcesView } from "@/views/sources-view";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [view, setView] = React.useState<ViewKey>("overview");
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [health, setHealth] = React.useState<Health | null>(null);
  const [healthLoading, setHealthLoading] = React.useState(true);

  const [normalHistory, setNormalHistory] = React.useState<ViewMessage[]>([]);
  const [hallufixHistory, setHallufixHistory] = React.useState<ViewMessage[]>([]);
  const [hybridHistory, setHybridHistory] = React.useState<ViewMessage[]>([]);

  const [loading, setLoading] = React.useState<Record<string, boolean>>({});
  const [error, setError] = React.useState<Record<string, string | null>>({});

  const refreshHealth = React.useCallback(async () => {
    setHealthLoading(true);
    try {
      setHealth(await getHealth());
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refreshHealth();
    const interval = setInterval(() => {
      void refreshHealth();
    }, 4000);
    return () => clearInterval(interval);
  }, [refreshHealth]);

  const send = async (
    kind: "normal" | "hallufix" | "hybrid",
    question: string,
    prev: ViewMessage[]
  ) => {
    const userMsg: ViewMessage = { role: "user", content: question };
    const withUser = [...prev, userMsg];
    const set = (fn: (prevNow: ViewMessage[]) => ViewMessage[]) => {
      if (kind === "normal") setNormalHistory(fn);
      else if (kind === "hallufix") setHallufixHistory(fn);
      else setHybridHistory(fn);
    };
    set((now) => [...now, userMsg]);
    setLoading((s) => ({ ...s, [kind]: true }));
    setError((s) => ({ ...s, [kind]: null }));

    const chatHistory: ChatMessage[] = withUser.map(({ role, content }) => ({ role, content }));
    try {
      let meta: RenderedMeta;
      if (kind === "normal") {
        const res = await normalChat(question, chatHistory);
        meta = { ...res, mode: "LLM" };
      } else if (kind === "hallufix") {
        meta = (await hallufixAsk(question, chatHistory)) as RenderedMeta;
      } else {
        meta = (await hybridChat(question, chatHistory)) as RenderedMeta;
      }
      const assistantMsg: ViewMessage = { role: "assistant", content: meta.answer ?? "", meta };
      set((now) => [...now, assistantMsg]);
    } catch (e) {
      setError((s) => ({ ...s, [kind]: e instanceof Error ? e.message : "Request failed." }));
    } finally {
      setLoading((s) => ({ ...s, [kind]: false }));
    }
  };

  const canSend = !!health?.ollama_running;

  return (
    <div className="flex h-[100dvh] w-full flex-col md:flex-row overflow-hidden bg-background text-foreground">
      {/* Mobile Top Header */}
      <header className="flex md:hidden items-center justify-between border-b bg-background/95 px-3 py-2.5 backdrop-blur-sm shrink-0 z-30">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileOpen(true)}
            className="size-8.5 shrink-0 text-foreground"
            aria-label="Open navigation menu"
          >
            <Menu className="size-5" />
          </Button>
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-lg bg-foreground text-xs font-bold text-background">
              T
            </div>
            <span className="text-sm font-semibold tracking-tight">TrustRAG</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-full border bg-card/80 px-2.5 py-1 text-xs">
            <span
              className={cn(
                "size-2 rounded-full",
                canSend ? "bg-emerald-500 animate-pulse" : "bg-red-500"
              )}
            />
            <span className="font-mono text-[11px] text-muted-foreground">
              {canSend ? "Online" : "Offline"}
            </span>
          </div>
        </div>
      </header>

      <Sidebar
        active={view}
        onSelect={setView}
        health={health}
        healthLoading={healthLoading}
        onRefresh={refreshHealth}
        apiUrl={API_URL}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <main className="min-w-0 flex-1 overflow-hidden flex flex-col">
        {view === "overview" && (
          <OverviewView
            health={health}
            healthLoading={healthLoading}
            normalHistory={normalHistory}
            hallufixHistory={hallufixHistory}
            hybridHistory={hybridHistory}
            onNavigate={setView}
          />
        )}
        {view === "normal" && (
          <NormalView
            history={normalHistory}
            loading={!!loading.normal}
            error={error.normal ?? null}
            onSend={(q) => void send("normal", q, normalHistory)}
            canSend={canSend}
          />
        )}
        {view === "hallufix" && (
          <HallufixView
            history={hallufixHistory}
            loading={!!loading.hallufix}
            error={error.hallufix ?? null}
            onSend={(q) => void send("hallufix", q, hallufixHistory)}
            canSend={canSend}
          />
        )}
        {view === "hybrid" && (
          <HybridView
            history={hybridHistory}
            loading={!!loading.hybrid}
            error={error.hybrid ?? null}
            onSend={(q) => void send("hybrid", q, hybridHistory)}
            canSend={canSend}
          />
        )}
        {view === "sources" && <SourcesView />}
      </main>
    </div>
  );
}