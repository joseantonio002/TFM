#!/usr/bin/env python3
"""Preload cached resources required by the connector."""

import os
from pathlib import Path

import language_tool_python
from sentence_transformers import SentenceTransformer

LANGUAGE_TOOL_VERSION = "6.6"

def ensure_cache_directories() -> None:
  """Create the cache directories used during image build and runtime."""
  cache_paths: list[str] = [
    os.environ.get("LTP_PATH", ""),
    os.environ.get("SENTENCE_TRANSFORMERS_HOME", ""),
    os.environ.get("HF_HOME", ""),
  ]

  for cache_path in cache_paths:
    if cache_path:
      Path(cache_path).mkdir(parents=True, exist_ok=True)


def preload_language_tool() -> None:
  """Download and warm the LanguageTool cache for Spanish."""
  print(f"LTP_PATH={os.environ.get('LTP_PATH')}")
  print(f"LANGUAGE_TOOL_VERSION={LANGUAGE_TOOL_VERSION}")

  with language_tool_python.LanguageTool(
      "es-ES",
      language_tool_download_version=LANGUAGE_TOOL_VERSION,
  ) as tool:
    tool.correct("Texto de prueba para inicializar LanguageTool.")


def preload_sentence_transformer() -> None:
  """Download and warm the sentence-transformers cache."""
  print(f"SENTENCE_TRANSFORMERS_HOME={os.environ.get('SENTENCE_TRANSFORMERS_HOME')}")
  print(f"HF_HOME={os.environ.get('HF_HOME')}")

  model: SentenceTransformer = SentenceTransformer("BAAI/bge-m3")
  model.encode(["texto de prueba para inicializar embeddings"])


def main() -> None:
  """Preload all model assets needed by the connector."""
  ensure_cache_directories()
  preload_language_tool()
  preload_sentence_transformer()
  print("Preloaded LanguageTool and sentence-transformers caches.")


if __name__ == "__main__":
  main()