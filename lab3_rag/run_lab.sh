#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$project_dir"

if [[ "${1:-}" != "--inside-nix" ]]; then
  flake_dir="$(mktemp -d "${TMPDIR:-/tmp}/lab3-flake.XXXXXXXX")"
  trap 'rm -f "$flake_dir/flake.nix" "$flake_dir/flake.lock"; rmdir "$flake_dir"' EXIT
  cp "$project_dir/flake.nix" "$project_dir/flake.lock" "$flake_dir/"
  nix develop "path:$flake_dir" --command bash "$project_dir/run_lab.sh" --inside-nix
  exit
fi

mkdir -p .cache

if ! ollama list >/dev/null 2>&1; then
  ollama serve >.cache/ollama.log 2>&1 &
  ollama_pid=$!
  trap 'kill "$ollama_pid" 2>/dev/null || true' EXIT

  for _ in {1..30}; do
    ollama list >/dev/null 2>&1 && break
    sleep 1
  done
fi

ollama list >/dev/null
ollama pull llama3.2:1b
ollama pull llama3.2:3b
ollama pull embeddinggemma

RAG_RERUN=1 jupyter nbconvert \
  --to notebook \
  --execute \
  --inplace \
  --ExecutePreprocessor.timeout=-1 \
  rag_experiments.ipynb

echo "Notebook completed: $project_dir/rag_experiments.ipynb"
