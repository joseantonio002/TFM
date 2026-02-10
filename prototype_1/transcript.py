#!/usr/bin/env python3
import json
import multiprocessing as mp
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model


BASE_DIR: Path = Path(__file__).resolve().parent
MODEL_NAME: str = "vosk-model-small-es-0.42"
MAX_PROCESSES: int = 3
MODEL: Model | None = None


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


def init_worker() -> None:
  """Load the Vosk model once per worker process."""
  global MODEL
  MODEL = Model(model_name=MODEL_NAME)


def find_full_audios(base_dir: Path) -> list[Path]:
  """Find every final WAV file inside pipeline folders."""
  full_audios: list[Path] = []
  for pipeline_dir in base_dir.iterdir():
    if not pipeline_dir.is_dir() or not pipeline_dir.name.startswith("pipeline_"):
      continue
    full_audios.extend(sorted(pipeline_dir.glob("*_full.wav")))
  return full_audios


def transcribe_audio(audio_path: Path) -> Path:
  """Transcribe one audio file and save the output text file."""
  if MODEL is None:
    raise RuntimeError("Worker model is not initialized.")

  source_id: str = audio_path.stem.removesuffix("_full")
  output_path: Path = audio_path.parent / f"{source_id}_transcription.txt"
  transcription: str = execute(MODEL, audio_path)
  output_path.write_text(transcription, encoding="utf-8")
  return output_path


def main() -> None:
  """Run multiprocessing transcription for all final audios."""
  audio_files: list[Path] = find_full_audios(BASE_DIR)

  if not audio_files:
    print("No *_full.wav files found in pipeline folders.")
    return

  with mp.Pool(processes=MAX_PROCESSES, initializer=init_worker) as pool:
    output_paths: list[Path] = pool.map(transcribe_audio, audio_files)

  for output_path in output_paths:
    print(f"Saved transcription: {output_path}")


if __name__ == "__main__":
  main()
