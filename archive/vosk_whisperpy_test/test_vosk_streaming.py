#!/usr/bin/env python3

import subprocess
import sys
import json
from vosk import Model, KaldiRecognizer, SetLogLevel

SAMPLE_RATE = 16000

SetLogLevel(0)

model = Model(model_name="vosk-model-small-es-0.42")
rec = KaldiRecognizer(model, SAMPLE_RATE)

with subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-i",
                            sys.argv[1],
                            "-ar", str(SAMPLE_RATE) , "-ac", "1", "-f", "s16le", "-"],
                            stdout=subprocess.PIPE) as process, open("output_stream_vosk.txt", "a", buffering=1) as o:

    while True:
        data = process.stdout.read(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            #print(rec.Result())
           res = json.loads(rec.Result()) 
           o.write(res["text"] + "\n")    

