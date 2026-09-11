"""CLI entry point for creating the local handbook index."""
from __future__ import annotations
import argparse
from pathlib import Path
from .ingest import ingest_paths
from .vectorstore import LocalVectorStore

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="data", help="A PDF/TXT file or directory of source files")
    parser.add_argument("--index-dir", default="data/index")
    args = parser.parse_args()
    source = Path(args.source)
    paths = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in {".pdf", ".txt"})
    chunks = ingest_paths(paths)
    store = LocalVectorStore(args.index_dir); store.build(chunks); store.save()
    print(f"Indexed {len(chunks)} chunks from {len(paths)} source file(s) into {args.index_dir}")
