"""Run the full TV/Radio connector pipeline in sequence."""

import argparse
import multiprocessing as mp
from pathlib import Path
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
    "-m",
    choices=["tiny", "base", "small"],
    dest="whisper_model",
    help="Optional whisper model to use for transcription.",
  )
  return parser.parse_args()


def run_step(step_name: str, step_callable: Any, *args: Any, **kwargs: Any) -> None:
  """Execute one pipeline step and print progress."""
  print(f"[STEP] {step_name}")
  step_callable(*args, **kwargs)


def build_pipeline_dirs(input_urls: list[str]) -> list[Path]:
  """Build expected dev pipeline directories from the configured sources."""
  selected_metadata: list[extract_audio.SourceMetadata] = extract_audio.load_metadata_from_environment(len(input_urls))
  selected_sources: list[extract_audio.Source] = extract_audio.build_sources_from_urls(input_urls, selected_metadata)
  script_dir: Path = Path(__file__).resolve().parent
  return [script_dir / f"pipeline_{source.source_id}" for source in selected_sources]


def main() -> None:
  """Run all connector pipeline steps sequentially."""
  args: argparse.Namespace = parse_args()
  input_urls: list[str] = list(args.input_urls)
  pipeline_dirs: list[Path] = build_pipeline_dirs(input_urls)
  start_datetime_text: str = extract_audio.write_execution_starting_date()
  transcription_stop_event: Any = mp.Event()
  print(f"Using whisper model: {args.whisper_model}" if args.whisper_model else "Using default whisper model small")
  transcription_workers: list[mp.Process] = transcript_segments_cpp.start_transcription_workers(
    pipeline_dirs=pipeline_dirs,
    stop_event=transcription_stop_event,
    start_datetime_text=start_datetime_text,
    whisper_model=args.whisper_model,
  )

  extraction_error: BaseException | None = None
  try:
    run_step(
      "1/4 extract_audio + transcript_segments_cpp",
      extract_audio.main,
      input_urls=input_urls,
      total_duration=args.total_duration,
      write_start_datetime=False,
    )
  except BaseException as error:
    extraction_error = error
  finally:
    transcription_stop_event.set()

  run_step("2/4 transcript_segments_cpp", transcript_segments_cpp.join_transcription_workers, transcription_workers)
  if extraction_error is not None:
    raise extraction_error
  run_step("3/4 merge_transcriptions", merge_transcriptions.main)
  run_step("4/4 segment_embeddings", segment_embeddings.main)


if __name__ == "__main__":
  main()
