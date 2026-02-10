#!/usr/bin/env python3
import json
import multiprocessing as mp
import wave
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from vosk import KaldiRecognizer, Model


BASE_DIR: Path = Path(__file__).resolve().parent
MODEL_NAME: str = "vosk-model-small-es-0.42"
MAX_PROCESSES: int = 3
MODEL: Model | None = None
START_DATETIME: datetime | None = None
SOURCES_DATA: dict[str, Any] | None = None

TYPE_FIELD_SOURCE: str = "type"
NAME_FIELD_SOURCE: str = "name"

def execute(model: Model, audio_path: Path) -> str:
  """Transcribe the audio file with a preloaded Vosk model."""
  with wave.open(str(audio_path), "rb") as wf:
    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
      raise ValueError("Audio file must be WAV format mono PCM.")

    rec = KaldiRecognizer(model, wf.getframerate())
    transcripts: list[str] = []

    while True:
      data = wf.readframes(4000)
      if len(data) == 0:
        break
      if rec.AcceptWaveform(data):
        result = json.loads(rec.Result())
        transcripts.append(result["text"])

    final_result = json.loads(rec.FinalResult())
    transcripts.append(final_result["text"])
    return "\n".join(transcripts)


def init_worker(start_datetime_text: str, sources_data: dict[str, Any]) -> None:
  """Load shared worker resources once per worker process."""
  global MODEL
  global START_DATETIME
  global SOURCES_DATA
  MODEL = Model(model_name=MODEL_NAME)
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
  if MODEL is None:
    raise RuntimeError("Worker model is not initialized.")
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
  transcription: str = execute(MODEL, audio_path)
  s_dt: datetime = START_DATETIME

  with wave.open(str(audio_path), "rb") as wf:
    duration_seconds: float = wf.getnframes() / wf.getframerate()

  e_dt: datetime = s_dt + timedelta(seconds=duration_seconds)

  final_json: dict[str, str] = {
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
