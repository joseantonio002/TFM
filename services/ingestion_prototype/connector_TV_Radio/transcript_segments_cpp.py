#!/usr/bin/env python3
import json
import multiprocessing as mp
import re
import subprocess
import wave
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
WHISPER_CLI_PATH: Path = (BASE_DIR / "../whisper.cpp/build/bin/whisper-cli").resolve()
WHISPER_MODEL_PATH: Path = (BASE_DIR / "../whisper.cpp/models/ggml-tiny.bin").resolve()
MAX_PROCESSES: int = 3
START_DATETIME: datetime | None = None
SOURCES_DATA: dict[str, Any] | None = None

TYPE_FIELD_SOURCE: str = "type"
NAME_FIELD_SOURCE: str = "name"
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


def init_worker(start_datetime_text: str, sources_data: dict[str, Any]) -> None:
  """Load shared worker resources once per worker process."""
  global START_DATETIME
  global SOURCES_DATA
  START_DATETIME = datetime.strptime(start_datetime_text, "%d/%m/%Y:%H:%M:%S")
  SOURCES_DATA = sources_data


def find_full_audios(base_dir: Path) -> list[Path]:
  """Find every final WAV file inside pipeline folders."""
  full_audios: list[Path] = []
  for pipeline_dir in base_dir.iterdir():
    if not pipeline_dir.is_dir() or not pipeline_dir.name.startswith("pipeline_"):
      continue
    full_audios.extend(sorted(pipeline_dir.glob("*_full.wav")))
  return full_audios


def transcribe_audio(audio_path: Path) -> Path:
  """Transcribe one audio file and save the output JSON file."""
  if START_DATETIME is None:
    raise RuntimeError("Worker start datetime is not initialized.")
  if SOURCES_DATA is None:
    raise RuntimeError("Worker sources data is not initialized.")

  segment_files: list[Path] = sorted(audio_path.parent.glob("*_out_00000.wav"))
  if not segment_files:
    raise ValueError(f"No source segment file found in {audio_path.parent}")

  source_id: str = segment_files[0].stem.removesuffix("_out_00000")
  source_data_raw: Any = SOURCES_DATA.get(source_id)
  if not isinstance(source_data_raw, dict):
    raise ValueError(f"Source ID '{source_id}' not found in sources.json")

  source_type_raw: Any = source_data_raw.get(TYPE_FIELD_SOURCE)
  source_name_raw: Any = source_data_raw.get(NAME_FIELD_SOURCE)
  source_type: str = str(source_type_raw).strip()
  source_name: str = str(source_name_raw).strip()
  if not source_type:
    raise ValueError(f"Missing '{TYPE_FIELD_SOURCE}' for source ID '{source_id}'")
  if not source_name:
    raise ValueError(f"Missing '{NAME_FIELD_SOURCE}' for source ID '{source_id}'")

  output_path: Path = audio_path.parent / f"{source_id}_transcription.json"
  raw_transcription: str = execute(audio_path)
  transcription: dict[str, str] = parse_transcription_segments(raw_transcription)
  s_dt: datetime = START_DATETIME

  with wave.open(str(audio_path), "rb") as wf:
    duration_seconds: float = wf.getnframes() / wf.getframerate()

  e_dt: datetime = s_dt + timedelta(seconds=duration_seconds)

  final_json: dict[str, Any] = {
    "transcription": transcription,
    "channel": source_name,
    "source_type": source_type,
    "s_datetime": s_dt.strftime("%d/%m/%Y:%H:%M:%S"),
    "e_datetime": e_dt.strftime("%d/%m/%Y:%H:%M:%S"),
  }
  output_path.write_text(json.dumps(final_json, ensure_ascii=False, indent=2), encoding="utf-8")
  return output_path


def main() -> None:
  """Run multiprocessing transcription for all final audios."""

  validate_whisper_paths()
  audio_files: list[Path] = find_full_audios(BASE_DIR)
  start_datetime_path: Path = BASE_DIR / "execution_starting_date.txt"
  sources_path: Path = BASE_DIR / "sources.json"
  start_datetime_text: str = start_datetime_path.read_text(encoding="utf-8").strip()
  sources_data: Any = json.loads(sources_path.read_text(encoding="utf-8"))

  if not start_datetime_text:
    raise ValueError(f"Empty starting datetime in {start_datetime_path}")
  if not isinstance(sources_data, dict):
    raise ValueError(f"Invalid sources content in {sources_path}")

  if not audio_files:
    print("No *_full.wav files found in pipeline folders.")
    return

  with mp.Pool(
    processes=MAX_PROCESSES,
    initializer=init_worker,
    initargs=(start_datetime_text, sources_data),
  ) as pool:
    output_paths: list[Path] = pool.map(transcribe_audio, audio_files)

  for output_path in output_paths:
    print(f"Saved transcription: {output_path}")


if __name__ == "__main__":
  main()
