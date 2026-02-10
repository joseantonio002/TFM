#!/usr/bin/env python3  
import wave  
import json  
from vosk import Model, KaldiRecognizer  
import time


# Load model (downloads automatically if not present)  
model = Model(model_name="vosk-model-small-es-0.42")  
  
# Open audio file  
wf = wave.open("experiment_fixed.wav", "rb")  
if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":  
    print("Audio file must be WAV format mono PCM.")  
    exit(1)  
  
# Create recognizer  
rec = KaldiRecognizer(model, wf.getframerate())  
  
s = time.time()
# Process audio  
with open("output_test_vosk.txt", "w") as out_file:  
    while True:  
        data = wf.readframes(4000)  
        if len(data) == 0:  
            break  
        if rec.AcceptWaveform(data):  
            result = json.loads(rec.Result())  
            out_file.write(result["text"] + "\n")  
      
    # Write final result  
    final_result = json.loads(rec.FinalResult())  
    out_file.write(final_result["text"] + "\n")
e = time.time()

print(f"time: {e - s}")
