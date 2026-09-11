"use client";

import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Percent,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import * as React from "react";

import type { Mode, RenderedMeta } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

function modeStyles(mode: Mode) {
  if (mode === "RAG") return "border-foreground/20 bg-foreground text-background";
  if (mode === "ABSTAIN") return "border-destructive/30 bg-destructive/10 text-destructive";
  return "border-transparent bg-secondary text-secondary-foreground";
}

function ModeBadge({ mode }: { mode: Mode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[11px] font-semibold",
        modeStyles(mode)
      )}
    >
      {mode === "ABSTAIN" && <ShieldAlert className="size-3" />}
      {mode}
    </span>
  );
}

export function CollapsibleSources({
  sources,
}: {
  sources: { citation: string; similarity_score: number; text: string }[];
}) {
  const [open, setOpen] = React.useState(false);
  const visible = open ? sources : sources.slice(0, 2);

  if (sources.length === 0) return null;

  return (
    <div className="mt-3 overflow-hidden rounded-lg border bg-background">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium hover:bg-accent/50"
      >
        <span className="flex items-center gap-1.5">
          <BookOpenCheck className="size-3.5 text-muted-foreground" />
          Sources ({sources.length})
        </span>
        {open ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
      </button>
      <Separator />
      <div className="space-y-2 px-3 py-2">
        {visible.map((s, i) => (
          <div key={i} className="text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono font-medium">{s.citation}</span>
              <span className="text-muted-foreground">sim {s.similarity_score.toFixed(3)}</span>
            </div>
            <p className="mt-0.5 line-clamp-3 text-muted-foreground">{s.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function VerificationList({ claims }: { claims: RenderedMeta["verification"] }) {
  if (!claims || claims.length === 0) return null;
  return (
    <div className="mt-3 space-y-1.5">
      <div className="text-xs font-medium text-muted-foreground">Claim verification</div>
      {claims.map((v, i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg border bg-background px-3 py-2 text-xs">
          {v.supported ? (
            <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
          ) : (
            <XCircle className="mt-0.5 size-3.5 shrink-0 text-destructive" />
          )}
          <div className="min-w-0 flex-1">
            <div className={cn("leading-snug", !v.supported && "line-through opacity-60")}>
              {v.claim}
            </div>
            {!v.supported && v.reason && (
              <div className="mt-0.5 text-muted-foreground">{v.reason}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Renders the pipeline metadata card under an assistant message. */
export function RAGMeta({ meta }: { meta: RenderedMeta }) {
  if (!meta || !meta.mode) return null;
  const { mode, confidence, latency_ms, stats, reason, abstained, sources, verification } = meta;

  return (
    <div className="mt-3 rounded-lg border bg-card/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <ModeBadge mode={mode} />
        {typeof confidence === "number" && (
          <Badge variant="outline" className="gap-1">
            <Percent className="size-3" /> {Math.round(confidence * 100)}%
          </Badge>
        )}
        {typeof latency_ms === "number" && (
          <Badge variant="outline" className="gap-1">
            <Clock className="size-3" /> {(latency_ms / 1000).toFixed(1)}s
          </Badge>
        )}
        {typeof stats?.support_rate === "number" && (
          <Badge variant="outline" className="gap-1">
            support {(stats.support_rate * 100).toFixed(0)}%
          </Badge>
        )}
      </div>

      {reason && <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{reason}</p>}

      {abstained && (
        <div className="mt-2 flex items-center gap-2 rounded-md bg-destructive/5 px-2.5 py-1.5 text-xs text-destructive">
          <AlertTriangle className="size-3.5" />
          The pipeline abstained — no reliable, evidence-backed answer was found.
        </div>
      )}

      {sources && sources.length > 0 && <Separator className="my-3" />}
      {sources && <CollapsibleSources sources={sources} />}

      {(verification?.length ?? 0) > 0 && <Separator className="my-3" />}
      {verification && <VerificationList claims={verification} />}
    </div>
  );
}