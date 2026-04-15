#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any

from nltk.tokenize import TextTilingTokenizer


BASE_DIR: Path = Path(__file__).resolve().parent
TRANSCRIPTION_PATH: Path = BASE_DIR / "pipeline_Onda Cero (España)" / "5_transcription_merged.json"
TIMESTAMP_PATTERN: re.Pattern[str] = re.compile(
  r"^\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}\]$"
)


def timestamp_sort_key(timestamp: str) -> tuple[int, int, int, int]:
  """Build a sortable tuple from the timestamp start time."""
  match: re.Match[str] | None = TIMESTAMP_PATTERN.match(timestamp.strip())
  if match is None:
    raise ValueError(f"Invalid timestamp format: {timestamp}")
  hours: int = int(match.group(1))
  minutes: int = int(match.group(2))
  seconds: int = int(match.group(3))
  milliseconds: int = int(match.group(4))
  return hours, minutes, seconds, milliseconds


def build_full_text(transcription_path: Path) -> str:
  """Merge all timestamped chunks into one text with paragraph breaks."""
  data: Any = json.loads(transcription_path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"Invalid JSON structure in {transcription_path}")

  transcription_raw: Any = data.get("transcription")
  if not isinstance(transcription_raw, dict):
    raise ValueError(f"Missing or invalid 'transcription' in {transcription_path}")

  ordered_timestamps: list[str] = sorted(transcription_raw.keys(), key=timestamp_sort_key)
  text_blocks: list[str] = []
  for timestamp in ordered_timestamps:
    segment_text_raw: Any = transcription_raw.get(timestamp)
    if not isinstance(segment_text_raw, str):
      raise ValueError(f"Invalid text value for timestamp {timestamp}")
    segment_text: str = segment_text_raw.strip()
    if segment_text:
      text_blocks.append(segment_text)

  return "\n\n".join(text_blocks)


def main() -> None:
  """Run TextTiling on merged transcription text and print segments."""
  full_text: str = build_full_text(TRANSCRIPTION_PATH)
  tokenizer: TextTilingTokenizer = TextTilingTokenizer()
  segments: list[str] = tokenizer.tokenize(full_text)

  print(f"Input file: {TRANSCRIPTION_PATH}")
  print(f"Merged text length: {len(full_text)} characters")
  print(f"TextTiling segments: {len(segments)}")

  for index, segment in enumerate(segments, start=1):
    print(f"\n--- Segment {index} ---\n")
    print(segment.strip())


if __name__ == "__main__":
  main()
