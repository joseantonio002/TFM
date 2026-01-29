import subprocess

URL = "http://dispatcher.rndfnk.com/crtve/rne5/vit/mp3/high"
OUT = "radio_10s.mp3"

cmd = [
    "ffmpeg",
    "-y",
    "-i", URL,
    "-t", "10",
    "-c", "copy",
    OUT
]

print("Running:", " ".join(cmd))
subprocess.run(cmd, check=True)
print("Saved:", OUT)