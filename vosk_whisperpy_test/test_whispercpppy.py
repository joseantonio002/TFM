import statistics
import time

from whispercpp import Whisper


def execute(whisper_model: Whisper) -> str:
  """Transcribe audio and extract text with a preloaded model."""
  result = whisper_model.transcribe("experiment.wav")
  text = whisper_model.extract_text(result)
  return text


times: list[float] = []

# Load models
w = Whisper("tiny")

# warm-up
for _ in range(2):
  execute(w)

# measured runs
for _ in range(30):
  start = time.perf_counter()
  execute(w)
  end = time.perf_counter()
  times.append(end - start)

print("avg:", statistics.mean(times))
print("min:", min(times))
print("std:", statistics.stdev(times))
