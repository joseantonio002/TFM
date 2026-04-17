"""Run the full TV/Radio connector pipeline in sequence."""

import argparse
from typing import Any

import extract_audio
import merge_transcriptions
import segment_embeddings
import transcript_segments_cpp


def parse_args() -> argparse.Namespace:
  """Parse the pipeline arguments forwarded to audio extraction."""
  parser: argparse.ArgumentParser = argparse.ArgumentParser(
    description="Run the full TV/Radio ingestion pipeline"
  )
  parser.add_argument(
    "-i",
    nargs="+",
    required=True,
    dest="input_urls",
    help="One or more source URLs separated by spaces.",
  )
  parser.add_argument(
    "-t",
    required=True,
    dest="total_duration",
    help="Total recording duration: integer minutes or HH:MM:SS(.msec)",
  )
  parser.add_argument(
    "-sw",
    type=int,
    dest="segment_wrap",
    help="Optional ffmpeg segment_wrap value (int > 0)",
  )
  parser.add_argument(
    "-st",
    dest="segment_time",
    help="Optional segment_time: integer minutes or HH:MM:SS(.msec)",
  )
  return parser.parse_args()


def run_step(step_name: str, step_callable: Any, *args: Any, **kwargs: Any) -> None:
  """Execute one pipeline step and print progress."""
  print(f"[STEP] {step_name}")
  step_callable(*args, **kwargs)


def main() -> None:
  """Run all connector pipeline steps sequentially."""
  args: argparse.Namespace = parse_args()

  run_step(
    "1/4 extract_audio",
    extract_audio.main,
    input_urls=list(args.input_urls),
    total_duration=args.total_duration,
    segment_wrap=args.segment_wrap,
    segment_time=args.segment_time,
  )
  run_step("2/4 transcript_segments_cpp", transcript_segments_cpp.main)
  run_step("3/4 merge_transcriptions", merge_transcriptions.main)
  run_step("4/4 segment_embeddings", segment_embeddings.main)


if __name__ == "__main__":
  main()
