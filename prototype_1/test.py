import subprocess

subprocess.Popen([
    "ffmpeg", "-nostdin", 
    "-reconnect", "1", "-reconnect_at_eof", "1",  "-reconnect_streamed", "1", "-reconnect_on_http_error", "4xx,5xx", "-reconnect_delay_max", "5",
    "-i", "https://d32rw80ytx9uxs.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-vlldndmow4yre/24HES.m3u8",
    "-vn", "-c:a", "copy", "-t", "00:00:30",
    "-f", "segment", "-segment_time", "10", "-reset_timestamps", "1",
    "out_%05d.m4a"
])
