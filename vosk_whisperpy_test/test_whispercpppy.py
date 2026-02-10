from whispercpp import Whisper
import time

w = Whisper('tiny')

s = time.time()
result = w.transcribe("experiment.wav")
text = w.extract_text(result)
e = time.time()
print(f"time: {e - s}")
