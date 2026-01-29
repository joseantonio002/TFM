# Script de python que captura 10 segundos del streaming en URL. 
# La URL tiene que ser la del proveedor (master.m3u8 normalmente) para que funcione ffmpeg
import subprocess

URL = "https://directes-tv-int.3catdirectes.cat/live-content/beauties-hls/master.m3u8"
OUT = "sample_10s.mp4"

cmd = [
    "ffmpeg",
    "-y",                 # overwrite
    "-i", URL,
    "-t", "10",           # 10 seconds
    "-c:v", "libx264",    # re-encode video
    "-c:a", "aac",        # re-encode audio
    "-movflags", "+faststart",
    OUT
]

print("Running:", " ".join(cmd))
subprocess.run(cmd, check=True)
print("Saved:", OUT)

