#!/usr/bin/env python3
import statistics
import subprocess
import time


def execute() -> str:
  """Run whisper-cli transcription command once."""
  command: list[str] = [
    "../whisper.cpp/build/bin/whisper-cli",
    "-m",
    "../whisper.cpp/models/ggml-tiny-q5_0.bin",
    "-l",
    "es",
    "-f",
    "experiment.wav",
  ]
  result = subprocess.run(command, check=True, capture_output=True, text=True)
  return result.stdout


times: list[float] = []

# Load models
execute()

# warm-up
for _ in range(2):
  execute()

# measured runs
for _ in range(6):
  start = time.perf_counter()
  execute()
  end = time.perf_counter()
  times.append(end - start)

print("avg:", statistics.mean(times))
print("min:", min(times))
print("std:", statistics.stdev(times))
