import subprocess

URL = "https://directes-tv-int.3catdirectes.cat/live-content/beauties-hls/master.m3u8"
OUT = "sample_10s_audio.m4a"

cmd = [
    "ffmpeg",
    "-y",
    "-i", URL,
    "-t", "10",
    "-vn",              # no video
    "-c:a", "copy",     # copy audio if possible
    OUT
]

print("Running:", " ".join(cmd))
subprocess.run(cmd, check=True)
print("Saved:", OUT)
