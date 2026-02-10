#!/usr/bin/env python3
import json
import multiprocessing as mp
import wave
from datetime import datetime, timedelta
from pathlib import Path

from vosk import KaldiRecognizer, Model


BASE_DIR: Path = Path(__file__).resolve().parent
MODEL_NAME: str = "vosk-model-small-es-0.42"
MAX_PROCESSES: int = 3
MODEL: Model | None = None
START_DATETIME: datetime | None = None


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


def init_worker(start_datetime_text: str) -> None:
  """Load shared worker resources once per worker process."""
  global MODEL
  global START_DATETIME
  MODEL = Model(model_name=MODEL_NAME)
  START_DATETIME = datetime.strptime(start_datetime_text, "%d/%m/%Y:%H:%M:%S")


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

  source_id: str = audio_path.stem.removesuffix("_full")
  output_path: Path = audio_path.parent / f"{source_id}_transcription.json"
  transcription: str = execute(MODEL, audio_path)
  s_dt: datetime = START_DATETIME

  with wave.open(str(audio_path), "rb") as wf:
    duration_seconds: float = wf.getnframes() / wf.getframerate()

  e_dt: datetime = s_dt + timedelta(seconds=duration_seconds)

  channel: str = audio_path.parent.name.removeprefix("pipeline_")
  final_json: dict[str, str] = {
    "transcription": transcription,
    "channel": channel,
    "s_datetime": s_dt.strftime("%d/%m/%Y:%H:%M:%S"),
    "e_datetime": e_dt.strftime("%d/%m/%Y:%H:%M:%S"),
  }
  output_path.write_text(json.dumps(final_json, ensure_ascii=False, indent=2), encoding="utf-8")
  return output_path


def main() -> None:
  """Run multiprocessing transcription for all final audios."""

  audio_files: list[Path] = find_full_audios(BASE_DIR)
  start_datetime_path: Path = BASE_DIR / "execution_starting_date.txt"
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
