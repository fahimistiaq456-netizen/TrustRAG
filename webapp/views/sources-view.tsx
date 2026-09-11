"use client";

import * as React from "react";
import {
  CheckCircle2,
  Database,
  FileText,
  FileUp,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";

import { getSourcesStatus, ingestFiles } from "@/lib/api";
import type { IngestResult, SourcesStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export function SourcesView() {
  const [status, setStatus] = React.useState<SourcesStatus>({ files: [], chunk_count: 0, index_ready: false });
  const [loading, setLoading] = React.useState(true);
  const [uploads, setUploads] = React.useState<File[]>([]);
  const [building, setBuilding] = React.useState(false);
  const [result, setResult] = React.useState<IngestResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    let active = true;
    const run = async () => {
      try {
        const s = await getSourcesStatus();
        if (active) setStatus(s);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Could not reach the backend.");
      } finally {
        if (active) setLoading(false);
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, []);

  const load = async () => {
    try {
      const s = await getSourcesStatus();
      setStatus(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the backend.");
    } finally {
      setLoading(false);
    }
  };

  const buildIndex = async () => {
    if (uploads.length === 0 || building) return;
    setBuilding(true);
    setError(null);
    setResult(null);
    try {
      const res = await ingestFiles(uploads);
      setResult(res);
      setUploads([]);
      if (inputRef.current) inputRef.current.value = "";
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Indexing failed.");
    } finally {
      setBuilding(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <header className="border-b bg-background/95 px-6 py-4 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-foreground text-background">
            <Database className="size-4" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">Source library</h1>
            <p className="text-sm text-muted-foreground">
              Embed your PDF / TXT sources locally; they are ranked at question time.
            </p>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-3xl flex-1 space-y-4 px-6 py-6">
        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <FileUp className="size-4" /> Add source documents
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.txt"
              multiple
              className="hidden"
              onChange={(e) => setUploads(Array.from(e.target.files ?? []))}
            />
            {uploads.length === 0 ? (
              <button
                onClick={() => inputRef.current?.click()}
                className="flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors hover:border-foreground/40 hover:bg-accent/40"
              >
                <FileText className="size-6 text-muted-foreground" />
                <span className="text-sm font-medium">Click to select files</span>
                <span className="text-xs text-muted-foreground">PDF or TXT</span>
              </button>
            ) : (
              <div className="space-y-2">
                {uploads.map((f, i) => (
                  <div
                    key={`${f.name}-${i}`}
                    className="flex items-center justify-between rounded-lg border bg-background px-3 py-2 text-sm"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <FileText className="size-4 shrink-0 text-muted-foreground" />
                      <span className="truncate">{f.name}</span>
                      <span className="text-xs text-muted-foreground">
                        ({(f.size / 1024).toFixed(1)} KB)
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => {
                        setUploads((prev) => prev.filter((_, j) => j !== i));
                        if (inputRef.current) inputRef.current.value = "";
                      }}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center gap-2">
              <Button onClick={buildIndex} disabled={uploads.length === 0 || building} className="flex-1">
                {building ? <Loader2 className="size-4 animate-spin" /> : null}
                {building ? "Indexing sources…" : "Build / refresh index"}
              </Button>
              {uploads.length > 0 && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setUploads([]);
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                >
                  Clear
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
{result && (
          <Card className="border-emerald-600/30 bg-emerald-50/40 dark:bg-emerald-950/20">
            <CardContent className="py-6">
              <div className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="size-4" /> Index built successfully
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {result.chunk_count} chunks from {result.source_count} sources ({result.files.join(", ")})
              </p>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Database className="size-4" /> Index status
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setLoading(true);
                  void load();
                }}
                disabled={loading}
                aria-label="Refresh"
              >
                <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> Loading…
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={status?.index_ready ? "default" : "secondary"}>
                    {status?.index_ready ? "Index ready" : "No index built"}
                  </Badge>
                  <Badge variant="outline">{status.chunk_count} chunks</Badge>
                </div>
                <Separator />
                {status?.files && status.files.length > 0 ? (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground">Stored sources</div>
                    {status.files.map((f) => (
                      <div key={f} className="flex items-center gap-2 text-sm">
                        <FileText className="size-3.5 text-muted-foreground" />
                        {f}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No sources stored yet. Upload a PDF or TXT and build the index.
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}