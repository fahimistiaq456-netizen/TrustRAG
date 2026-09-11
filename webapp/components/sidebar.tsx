"use client";

import {
  Database,
  LayoutDashboard,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Server,
  ShieldCheck,
  Shuffle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { Health } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ThemeToggle } from "@/components/theme-toggle";

export type ViewKey = "overview" | "normal" | "hallufix" | "hybrid" | "sources";

const NAV_ITEMS: { key: ViewKey; label: string; icon: React.ReactNode; hint: string }[] = [
  { key: "overview", label: "Overview", icon: <LayoutDashboard />, hint: "Status & comparison" },
  { key: "normal", label: "Normal chat", icon: <MessageSquareText />, hint: "Local model only" },
  { key: "hallufix", label: "TrustRAG", icon: <ShieldCheck />, hint: "Verified source answers" },
  { key: "hybrid", label: "Hybrid", icon: <Shuffle />, hint: "Source first, LLM fallback" },
  { key: "sources", label: "Sources", icon: <Database />, hint: "Index your documents" },
];

interface SidebarProps {
  active: ViewKey;
  onSelect: (view: ViewKey) => void;
  health: Health | null;
  healthLoading: boolean;
  onRefresh: () => void;
  apiUrl: string;
}

export function Sidebar({
  active,
  onSelect,
  health,
  healthLoading,
  onRefresh,
  apiUrl,
}: SidebarProps) {
  const ollamaOk = health?.ollama_running ?? false;

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r bg-neutral-950 text-neutral-100">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex size-9 items-center justify-center rounded-lg bg-white text-sm font-bold text-neutral-950">
          T
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight">TrustRAG</div>
          <div className="text-[11px] text-neutral-500">Local LLM Laboratory</div>
        </div>
      </div>

      <Separator className="bg-neutral-800" />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        <div className="px-2 pb-2 text-[11px] font-medium uppercase tracking-wider text-neutral-600">
          Workbench
        </div>
        {NAV_ITEMS.map((item) => {
          const isActive = active === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onSelect(item.key)}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                isActive
                  ? "bg-white font-medium text-neutral-950"
                  : "text-neutral-400 hover:bg-white/10 hover:text-white"
              )}
            >
              <span className={cn("[&_svg]:size-4", isActive ? "text-neutral-950" : "text-neutral-500")}>
                {item.icon}
              </span>
              <span className="flex-1">{item.label}</span>
              <span
                className={cn(
                  "hidden text-[11px]",
                  isActive ? "text-neutral-500" : "text-neutral-700"
                )}
              >
                {item.hint}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Status */}
      <div className="space-y-3 border-t border-neutral-800 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-neutral-400">
            <Server className="size-3.5 text-neutral-500" />
            <span className="font-mono">{apiUrl.replace(/^https?:\/\//, "")}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onRefresh}
            disabled={healthLoading}
            className="h-7 w-7 text-neutral-400 hover:bg-white/10 hover:text-white"
            aria-label="Refresh status"
          >
            <RefreshCw className={cn("size-3.5", healthLoading && "animate-spin")} />
          </Button>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-3 text-xs">
          {healthLoading ? (
            <div className="flex items-center gap-2 text-neutral-500">
              <Loader2 className="size-3.5 animate-spin" /> Checking backend…
            </div>
          ) : !health ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="size-2 rounded-full bg-red-500" />
                <span className="font-medium text-neutral-200">Backend offline</span>
              </div>
              <p className="text-[11px] leading-relaxed text-neutral-500">
                FastAPI is not running on {apiUrl.replace(/^https?:\/\//, "")}. Start it with{" "}
                <span className="font-mono text-neutral-400">./run_backend.sh</span> (or{" "}
                <span className="font-mono text-neutral-400">./run_all.sh</span>) and refresh.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "size-2 rounded-full",
                    ollamaOk ? "bg-emerald-400" : "bg-red-500"
                  )}
                />
                <span className="font-medium text-neutral-200">
                  Ollama {ollamaOk ? "online" : "offline"}
                </span>
              </div>
              <div className="mt-2 truncate font-mono text-[11px] text-neutral-500">
                {health?.selected_model ?? "unknown model"}
              </div>
              {health?.selected_model_available === false && (
                <p className="text-[11px] leading-relaxed text-amber-400">
                  Selected model is not pulled. Run{" "}
                  <span className="font-mono">ollama pull {health.selected_model}</span>.
                </p>
              )}
            </div>
          )}
        </div>

        <ThemeToggle />
      </div>
    </aside>
  );
}