import statistics
import time

from whispercpp import Whisper


def execute(whisper_model: Whisper) -> str:
  """Transcribe audio and extract text with a preloaded model."""
  result = whisper_model.transcribe("experiment_fixed.wav")
  text = whisper_model.extract_text(result)
  return text


times: list[float] = []

# Load models
w = Whisper("tiny")

text = execute(w) 

print(text)