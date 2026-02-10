#!/usr/bin/env python3
import json
import statistics
import time
import wave

from vosk import KaldiRecognizer, Model


def execute(model: Model) -> str:
  """Transcribe the audio file with a preloaded Vosk model."""
  with wave.open("experiment_fixed.wav", "rb") as wf:
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


times: list[float] = []

# Load models
model = Model(model_name="vosk-model-small-es-0.42")

# warm-up
for _ in range(2):
  execute(model)

# measured runs
for _ in range(30):
  start = time.perf_counter()
  execute(model)
  end = time.perf_counter()
  times.append(end - start)

print("avg:", statistics.mean(times))
print("min:", min(times))
print("std:", statistics.stdev(times))
