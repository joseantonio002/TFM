#!/usr/bin/env python3
import json
import multiprocessing as mp
import re
import subprocess
import wave
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


SCRIPT_DIR: Path = Path(__file__).resolve().parent
BASE_DIR: Path = SCRIPT_DIR.parent.parent
WHISPER_CLI_PATH: Path = (BASE_DIR / "../whisper.cpp/build/bin/whisper-cli").resolve()
WHISPER_MODEL_PATH: Path = (BASE_DIR / "../whisper.cpp/models/ggml-tiny.bin").resolve()
OUTPUT_DIR_RAW: Path = Path("./outputs/raw")
MAX_PROCESSES: int = 3
START_DATETIME: datetime | None = None
TIMESTAMP_PATTERN: re.Pattern[str] = re.compile(r"^\s*(\[[^\]]+\])\s*(.*)$")

def execute(audio_path: Path) -> str:
  """Run whisper-cli transcription command once."""
  command: list[str] = [
    str(WHISPER_CLI_PATH),
    "-m",
    str(WHISPER_MODEL_PATH),
    "-l",
    "es",
    "-t", # -t Number of threads to use (default: number of CPU cores)
    "1", # Avoid CPU oversubscription when using multiple Pool workers
    "-f",
    str(audio_path),
  ]
  # subprocess.run(..., text=True) tries to decode process output as UTF-8, 
  # but whisper-cli may output non-UTF-8 bytes, 
  # causing decoding errors. To avoid this, we capture output as bytes and decode 
  # manually with error handling.
  try:
    # Switched to byte capture to handle potential non-UTF-8 output from whisper-cli
    result: subprocess.CompletedProcess[bytes] = subprocess.run(
      command,
      check=True,
      capture_output=True,
    )
  except subprocess.CalledProcessError as error:
    stderr_text: str = error.stderr.decode("utf-8", errors="replace") if error.stderr else ""
    raise RuntimeError(f"whisper-cli failed for {audio_path}: {stderr_text}") from error

  # Safe decoding (errors="replace")
  stdout_text: str = result.stdout.decode("utf-8", errors="replace")
  if stdout_text.strip():
    return stdout_text
  return result.stderr.decode("utf-8", errors="replace")


def validate_whisper_paths() -> None:
  """Validate whisper-cli binary and model paths before processing."""
  if not WHISPER_CLI_PATH.is_file():
    raise FileNotFoundError(f"whisper-cli binary not found at {WHISPER_CLI_PATH}")
  if not WHISPER_MODEL_PATH.is_file():
    raise FileNotFoundError(f"whisper model not found at {WHISPER_MODEL_PATH}")


def parse_transcription_segments(raw_transcription: str) -> dict[str, str]:
  """Parse whisper-cli output into a timestamp-to-text dictionary."""
  transcription_by_timestamp: dict[str, str] = {}
  for line in raw_transcription.splitlines():
    match: re.Match[str] | None = TIMESTAMP_PATTERN.match(line)
    if match is None:
      continue

    timestamp: str = match.group(1).strip()
    text: str = match.group(2).strip()
    if not timestamp:
      continue

    if timestamp in transcription_by_timestamp and text:
      previous_text: str = transcription_by_timestamp[timestamp]
      merged_text: str = f"{previous_text} {text}".strip()
      transcription_by_timestamp[timestamp] = merged_text
      continue

    transcription_by_timestamp[timestamp] = text

  return transcription_by_timestamp


def init_worker(start_datetime_text: str) -> None:
  """Load shared worker resources once per worker process."""
  global START_DATETIME
  START_DATETIME = datetime.strptime(start_datetime_text, "%d/%m/%Y:%H:%M:%S")


def find_full_audios(base_dir: Path) -> list[Path]:
  """Find every final WAV file inside pipeline folders."""
  full_audios: list[Path] = []
  for pipeline_dir in base_dir.iterdir():
    if not pipeline_dir.is_dir() or not pipeline_dir.name.startswith("pipeline_"):
      continue
    full_audios.extend(sorted(pipeline_dir.glob("*_full.wav")))
  return full_audios


def load_pipeline_metadata(metadata_path: Path) -> dict[str, str]:
  """Load key=value metadata from a pipeline metadata file."""
  metadata: dict[str, str] = {}
  for line in metadata_path.read_text(encoding="utf-8").splitlines():
    if not line.strip() or "=" not in line:
      continue
    key, value = line.split("=", 1)
    metadata[key.strip()] = value.strip()
  return metadata


def sanitize_filename_part(raw_value: str) -> str:
  """Return a filesystem-safe filename fragment."""
  sanitized: str = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_value.strip())
  return sanitized.strip("_") or "unknown"


def build_output_dir() -> Path:
  """Resolve and create the transcription output directory."""
  output_dir: Path = OUTPUT_DIR_RAW if OUTPUT_DIR_RAW.is_absolute() else (SCRIPT_DIR / OUTPUT_DIR_RAW)
  output_dir.mkdir(parents=True, exist_ok=True)
  return output_dir


def build_output_path(output_dir: Path, metadata: dict[str, str]) -> Path:
  """Build a unique JSON output path from pipeline metadata."""
  connector_id: str = sanitize_filename_part(metadata.get("connector_id", "unknown_connector"))
  airflow_dag_id: str = sanitize_filename_part(metadata.get("airflow_dag_id", "unknown_dag"))
  executed_at: str = sanitize_filename_part(metadata.get("extracted_at", "unknown_datetime"))
  base_name: str = f"{connector_id}_{airflow_dag_id}_{executed_at}"
  output_path: Path = output_dir / f"{base_name}.json"

  if not output_path.exists():
    return output_path

  suffix: int = 1
  while True:
    candidate_path: Path = output_dir / f"{base_name}_{suffix}.json"
    if not candidate_path.exists():
      return candidate_path
    suffix += 1


def transcribe_audio(audio_path: Path) -> Path:
  """Transcribe one audio file and save the output JSON file."""
  if START_DATETIME is None:
    raise RuntimeError("Worker start datetime is not initialized.")
  metadata_path: Path = audio_path.parent / "metadata.txt"
  metadata: dict[str, str] = load_pipeline_metadata(metadata_path)
  output_dir: Path = build_output_dir()
  output_path: Path = build_output_path(output_dir, metadata)
  raw_transcription: str = execute(audio_path)
  transcription: dict[str, str] = parse_transcription_segments(raw_transcription)
  s_dt: datetime = START_DATETIME

  with wave.open(str(audio_path), "rb") as wf:
    duration_seconds: float = wf.getnframes() / wf.getframerate()

  e_dt: datetime = s_dt + timedelta(seconds=duration_seconds)

  final_json: dict[str, Any] = {
    "transcription": transcription,
    "channel": metadata.get("source_name", ""),
    "source_type": metadata.get("source_type", ""),
    "s_datetime": s_dt.strftime("%d/%m/%Y:%H:%M:%S"),
    "e_datetime": e_dt.strftime("%d/%m/%Y:%H:%M:%S"),
  }
  output_path.write_text(json.dumps(final_json, ensure_ascii=False, indent=2), encoding="utf-8")
  return output_path


def main() -> None:
  """Run multiprocessing transcription for all final audios."""

  validate_whisper_paths()
  audio_files: list[Path] = find_full_audios(SCRIPT_DIR)
  start_datetime_path: Path = SCRIPT_DIR / "execution_starting_date.txt"
  start_datetime_text: str = start_datetime_path.read_text(encoding="utf-8").strip()

  if not start_datetime_text:
    raise ValueError(f"Empty starting datetime in {start_datetime_path}")

  if not audio_files:
    print("No *_full.wav files found in pipeline folders.")
    return

  with mp.Pool(
    processes=MAX_PROCESSES,
    initializer=init_worker,
    initargs=(start_datetime_text,),
  ) as pool:
    output_paths: list[Path] = pool.map(transcribe_audio, audio_files)

  for output_path in output_paths:
    print(f"Saved transcription: {output_path}")


if __name__ == "__main__":
  main()
