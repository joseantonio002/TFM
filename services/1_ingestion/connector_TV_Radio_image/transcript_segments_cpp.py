#!/usr/bin/env python3
import json
import multiprocessing as mp
import re
import subprocess
import time
import wave
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


BASE_DIR: Path = Path(__file__).resolve()
WHISPER_CLI_PATH: Path = ("./whisper.cpp/build/bin/whisper-cli")
# ggml-base.bin ggml-small.bin 
WHISPER_MODELS_DIR: Path = Path("./whisper.cpp/models")
DEFAULT_WHISPER_MODEL_PATH: Path = WHISPER_MODELS_DIR / "ggml-small.bin"
WHISPER_MODEL_PATH: Path = DEFAULT_WHISPER_MODEL_PATH
WHISPER_MODEL_OPTIONS: set[str] = {"tiny", "base", "small"}
START_DATETIME: datetime | None = None
POLL_INTERVAL_SECONDS: float = 2.0

TIMESTAMP_PATTERN: re.Pattern[str] = re.compile(r"^\s*(\[[^\]]+\])\s*(.*)$")
SEGMENT_AUDIO_PATTERN: re.Pattern[str] = re.compile(r"^(?P<source_id>.+)_out_(?P<index>\d+)\.wav$")

def build_whisper_model_path(whisper_model: str | None) -> Path:
  """Build the whisper model path from an optional model name."""
  if whisper_model is None:
    return DEFAULT_WHISPER_MODEL_PATH
  if whisper_model not in WHISPER_MODEL_OPTIONS:
    raise ValueError(f"Invalid whisper model: {whisper_model}")
  return WHISPER_MODELS_DIR / f"ggml-{whisper_model}.bin"


def set_whisper_model_path(whisper_model: str | None) -> None:
  """Set the process-local whisper model path."""
  global WHISPER_MODEL_PATH
  WHISPER_MODEL_PATH = build_whisper_model_path(whisper_model)


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


def find_pipeline_dirs(base_dir: Path) -> list[Path]:
  """Find every pipeline directory that can contain segmented audio."""
  return sorted(
    pipeline_dir
    for pipeline_dir in base_dir.glob("pipeline_*")
    if pipeline_dir.is_dir()
  )


def parse_segment_audio_path(audio_path: Path) -> tuple[str, int]:
  """Extract source id and segment index from a segment audio path."""
  match: re.Match[str] | None = SEGMENT_AUDIO_PATTERN.match(audio_path.name)
  if match is None:
    raise ValueError(f"Invalid segment audio filename: {audio_path.name}")
  return match.group("source_id"), int(match.group("index"))


def find_segment_audios(pipeline_dir: Path) -> dict[int, Path]:
  """Find available segment WAV files keyed by their segment index."""
  segment_audios: dict[int, Path] = {}
  if not pipeline_dir.is_dir():
    return segment_audios

  for audio_path in sorted(pipeline_dir.glob("*_out_*.wav")):
    try:
      _, segment_index = parse_segment_audio_path(audio_path)
    except ValueError:
      continue
    segment_audios[segment_index] = audio_path
  return segment_audios


def load_pipeline_metadata(pipeline_dir: Path) -> dict[str, str]:
  """Load pipeline metadata.txt as a key-value mapping."""
  metadata_path: Path = pipeline_dir / "metadata.txt"
  if not metadata_path.is_file():
    raise FileNotFoundError(f"metadata.txt not found at {metadata_path}")

  metadata: dict[str, str] = {}
  for line in metadata_path.read_text(encoding="utf-8").splitlines():
    if not line.strip() or "=" not in line:
      continue
    key, value = line.split("=", 1)
    metadata[key.strip()] = value.strip()
  return metadata


def get_audio_duration_seconds(audio_path: Path) -> float:
  """Read the duration of a WAV file in seconds."""
  with wave.open(str(audio_path), "rb") as wf:
    return wf.getnframes() / wf.getframerate()


def build_segment_output_path(audio_path: Path) -> Path:
  """Build the transcription JSON path for one segment audio file."""
  return audio_path.with_suffix(".transcription.json")


def transcribe_audio_segment(
  audio_path: Path,
  start_datetime: datetime,
  segment_start_seconds: float,
) -> tuple[Path, float]:
  """Transcribe one segment audio file and save its JSON output."""
  source_id, segment_index = parse_segment_audio_path(audio_path)
  metadata: dict[str, str] = load_pipeline_metadata(audio_path.parent)
  source_type: str = metadata.get("source_type", "").strip()
  source_name: str = metadata.get("source_name", "").strip()
  if not source_type:
    raise ValueError(f"Missing 'source_type' in {audio_path.parent / 'metadata.txt'}")
  if not source_name:
    raise ValueError(f"Missing 'source_name' in {audio_path.parent / 'metadata.txt'}")

  output_path: Path = build_segment_output_path(audio_path)
  raw_transcription: str = execute(audio_path)
  transcription: dict[str, str] = parse_transcription_segments(raw_transcription)
  duration_seconds: float = get_audio_duration_seconds(audio_path)

  s_dt: datetime = start_datetime + timedelta(seconds=segment_start_seconds)
  e_dt: datetime = s_dt + timedelta(seconds=duration_seconds)

  final_json: dict[str, Any] = {
    "transcription": transcription,
    "channel": source_name,
    "source_type": source_type,
    "s_datetime": s_dt.strftime("%d/%m/%Y:%H:%M:%S"),
    "e_datetime": e_dt.strftime("%d/%m/%Y:%H:%M:%S"),
    "segment_audio_file": audio_path.name,
    "segment_index": segment_index,
    "segment_start_seconds": segment_start_seconds,
    "segment_duration_seconds": duration_seconds,
  }
  serialized_json: str = json.dumps(final_json, ensure_ascii=False, indent=2)
  output_path.write_text(serialized_json, encoding="utf-8")
  return output_path, duration_seconds


def transcribe_pipeline_segments(
  pipeline_dir: Path,
  stop_event: Any,
  start_datetime_text: str,
  whisper_model: str | None = None,
) -> None:
  """Transcribe one source pipeline directory sequentially as segments become ready."""
  set_whisper_model_path(whisper_model)
  start_datetime: datetime = datetime.strptime(start_datetime_text, "%d/%m/%Y:%H:%M:%S")
  next_segment_index: int = 0
  next_segment_start_seconds: float = 0.0

  while True:
    segment_audios: dict[int, Path] = find_segment_audios(pipeline_dir)
    candidate_audio: Path | None = segment_audios.get(next_segment_index)

    if candidate_audio is None:
      if stop_event.is_set():
        break
      time.sleep(POLL_INTERVAL_SECONDS)
      continue

    next_audio_exists: bool = (next_segment_index + 1) in segment_audios
    if not next_audio_exists and not stop_event.is_set():
      time.sleep(POLL_INTERVAL_SECONDS)
      continue

    if candidate_audio.stat().st_size == 0:
      time.sleep(POLL_INTERVAL_SECONDS)
      continue

    print(f"Starting transcription: {candidate_audio.name}", flush=True)
    output_path, duration_seconds = transcribe_audio_segment(
      audio_path=candidate_audio,
      start_datetime=start_datetime,
      segment_start_seconds=next_segment_start_seconds,
    )
    print(f"Finished transcription: {candidate_audio.name} -> {output_path}", flush=True)
    next_segment_start_seconds += duration_seconds
    next_segment_index += 1


def start_transcription_workers(
  pipeline_dirs: list[Path],
  stop_event: Any,
  start_datetime_text: str,
  whisper_model: str | None = None,
) -> list[mp.Process]:
  """Start one transcription process per source pipeline directory."""
  workers: list[mp.Process] = []
  for pipeline_dir in pipeline_dirs:
    worker: mp.Process = mp.Process(
      target=transcribe_pipeline_segments,
      args=(pipeline_dir, stop_event, start_datetime_text, whisper_model),
      name=f"transcribe_{pipeline_dir.name}",
    )
    worker.start()
    workers.append(worker)
  return workers


def join_transcription_workers(workers: list[mp.Process]) -> None:
  """Wait for transcription workers and raise if any failed."""
  failed_workers: list[str] = []
  for worker in workers:
    worker.join()
    if worker.exitcode not in (0, None):
      failed_workers.append(f"{worker.name}={worker.exitcode}")

  if failed_workers:
    raise RuntimeError(f"Transcription workers failed: {', '.join(failed_workers)}")


def main(pipeline_dirs: list[Path] | None = None, whisper_model: str | None = None) -> None:
  """Run one transcription process per source for all available segments."""
  selected_pipeline_dirs: list[Path] = pipeline_dirs or find_pipeline_dirs(Path(__file__).resolve().parent)
  start_datetime_path: Path = Path(__file__).resolve().parent / "./execution_starting_date.txt"
  start_datetime_text: str = start_datetime_path.read_text(encoding="utf-8").strip()

  if not start_datetime_text:
    raise ValueError(f"Empty starting datetime in {start_datetime_path}")

  if not selected_pipeline_dirs:
    print("No pipeline folders found.")
    return

  stop_event: Any = mp.Event()
  stop_event.set()
  workers: list[mp.Process] = start_transcription_workers(
    pipeline_dirs=selected_pipeline_dirs,
    stop_event=stop_event,
    start_datetime_text=start_datetime_text,
    whisper_model=whisper_model,
  )
  join_transcription_workers(workers)


if __name__ == "__main__":
  main()
