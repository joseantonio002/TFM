from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path
from typing import Optional

from sentence_transformers import SentenceTransformer

SCRIPT_DIR: Path = Path(__file__).resolve().parent
CONNECTOR_DIR: Path = SCRIPT_DIR.parent
if str(CONNECTOR_DIR) not in sys.path:
  sys.path.insert(0, str(CONNECTOR_DIR))

from segment_embeddings import (  # noqa: E402
  K,
  MIN_GAP_UNITS,
  PEAK_THRESHOLD,
  Unit,
  build_story_chunks,
  compute_boundary_scores,
  compute_embeddings,
  enforce_min_gap,
  pick_peak_candidates,
)

MODEL_NAME: str = "BAAI/bge-m3"
OUTPUT_DIR: Path = Path("segmented_news_outputs")
MAX_WORDS_PER_UNIT: int = 40


def split_long_unit(text: str, max_words: int) -> list[str]:
  """Split a long text unit into smaller word chunks."""
  words: list[str] = text.split()
  if len(words) <= max_words:
    return [text]

  chunks: list[str] = []
  for start_index in range(0, len(words), max_words):
    chunks.append(" ".join(words[start_index:start_index + max_words]))
  return chunks


def split_text_units(text: str) -> list[str]:
  """Split raw Spanish news text into semantic units for the algorithm."""
  stripped_text: str = text.strip()
  if not stripped_text:
    return []

  raw_units: list[str] = re.split(r"(?<=[.!?;:])\s+|\n+", stripped_text)
  units: list[str] = []
  for raw_unit in raw_units:
    clean_unit: str = re.sub(r"\s+", " ", raw_unit).strip()
    if not clean_unit:
      continue
    units.extend(split_long_unit(clean_unit, MAX_WORDS_PER_UNIT))

  return units


def build_text_units(text: str) -> list[Unit]:
  """Convert raw text into timestamp-like units without real timestamps."""
  text_units: list[str] = split_text_units(text)
  return [
    {"s": float(index), "e": float(index + 1), "text": unit_text}
    for index, unit_text in enumerate(text_units)
  ]


def save_news_files(news_items: list[str], output_dir: Optional[Path] = None) -> list[Path]:
  """Store each segmented news item in a random text file."""
  resolved_output_dir: Path = output_dir or (SCRIPT_DIR / OUTPUT_DIR)
  resolved_output_dir.mkdir(parents=True, exist_ok=True)

  output_paths: list[Path] = []
  for news_item in news_items:
    output_path: Path = resolved_output_dir / f"{uuid.uuid4().hex}.txt"
    output_path.write_text(news_item, encoding="utf-8")
    output_paths.append(output_path)

  return output_paths


def print_news(news_items: list[str]) -> None:
  """Print segmented news items separated by a visible divider."""
  separator: str = "---" * 20
  for index, news_item in enumerate(news_items):
    print(news_item)
    if index < len(news_items) - 1:
      print(separator)


def segment_algorithm(text: str, output_format: str = "print", output_dir: Optional[Path] = None) -> list[str]:
  """Segment raw news text using the same embedding boundary algorithm."""
  units: list[Unit] = build_text_units(text)
  if not units:
    return []

  model = SentenceTransformer(MODEL_NAME)
  embeddings = compute_embeddings(model, units)
  scores: list[float] = compute_boundary_scores(embeddings, K)
  candidates: list[int] = pick_peak_candidates(scores, PEAK_THRESHOLD)
  boundaries: list[int] = enforce_min_gap(candidates, scores, MIN_GAP_UNITS)
  news_items: list[str] = [story["text"] for story in build_story_chunks(units, boundaries)]

  if output_format == "print":
    print_news(news_items)
  elif output_format == "file":
    save_news_files(news_items, output_dir=output_dir)
  else:
    raise ValueError('output_format must be "print" or "file"')

  return news_items


def main() -> None:
  """Read raw text from standard input and print segmented news."""
  text: str = sys.stdin.read()
  segment_algorithm(text)


if __name__ == "__main__":
  main()
