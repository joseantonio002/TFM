

"""
ffmeg command to extract audio from a single streaming URL:
ffmpeg 
-reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_on_http_error 4xx,5xx -reconnect_delay_max 5
-nostdin 
-i URL 
-vn 
- t [-][HH:]MM:SS[.msec]
-c:a copy   
-f segment -segment_time X -segment_wrap Y -reset_timestamps 1   
"out_%05d.mp3"
"""

import subprocess






if __name__ == "__main__":
  pass
