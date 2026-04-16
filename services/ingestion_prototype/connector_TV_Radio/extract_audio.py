import asyncio
import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

TIME_PATTERN: re.Pattern[str] = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)$")
EXCEDING_TIME_BUFFER_SECONDS: int = 10


@dataclass(frozen=True)
class Source:
  source_id: str
  name: str
  url: str


def parse_time_value(raw_value: str, argument_name: str) -> float:
  """Convert a CLI time value into seconds."""
  value: str = raw_value.strip()
  if not value:
    raise ValueError(f"{argument_name} cannot be empty")

  if value.isdigit():
    minutes: int = int(value)
    if minutes <= 0:
      raise ValueError(f"{argument_name} minutes must be > 0")
    return float(minutes * 60)

  match: re.Match[str] | None = TIME_PATTERN.match(value)
  if match is None:
    raise ValueError(
      f"{argument_name} must be a positive integer (minutes) or HH:MM:SS(.msec)"
    )

  hours: int = int(match.group(1))
  minutes_part: int = int(match.group(2))
  seconds_part: float = float(match.group(3))

  if minutes_part >= 60:
    raise ValueError(f"{argument_name} minutes field must be < 60 in HH:MM:SS")
  if seconds_part >= 60:
    raise ValueError(f"{argument_name} seconds field must be < 60 in HH:MM:SS")

  total_seconds: float = (hours * 3600) + (minutes_part * 60) + seconds_part
  if total_seconds <= 0:
    raise ValueError(f"{argument_name} must be > 0 seconds")
  return total_seconds


def parse_args() -> argparse.Namespace:
  """Parse command-line arguments for audio extraction."""
  parser: argparse.ArgumentParser = argparse.ArgumentParser(
    description="Extract segmented audio from streaming sources in parallel"
  )
  parser.add_argument(
    "-i",
    nargs="+",
    required=True,
    dest="input_urls",
    help="One or more source URLs separated by spaces.",
  )
  parser.add_argument(
    "-t",
    required=True,
    dest="total_duration",
    help="Total recording duration: integer minutes or HH:MM:SS(.msec)",
  )
  parser.add_argument(
    "-sw",
    type=int,
    dest="segment_wrap",
    help="Optional ffmpeg segment_wrap value (int > 0)",
  )
  parser.add_argument(
    "-st",
    dest="segment_time",
    help="Optional segment_time: integer minutes or HH:MM:SS(.msec)",
  )
  return parser.parse_args()


def build_sources_from_urls(input_urls: list[str]) -> list[Source]:
  """Build source metadata directly from the provided input URLs."""
  sources: list[Source] = []
  for index, raw_url in enumerate(input_urls, start=1):
    url: str = raw_url.strip()
    if not url:
      raise ValueError("-i values cannot be empty")
    source_id: str = f"input_{index:02d}"
    sources.append(Source(source_id=source_id, name=source_id, url=url))
  return sources


def compute_segment_time_seconds(total_duration_seconds: int, raw_segment_time: str | None) -> int:
  """Resolve the segment duration in seconds."""
  if raw_segment_time is None:
    computed: int = int(round(total_duration_seconds * 0.2))
    return max(1, computed)

  segment_time_seconds: float = parse_time_value(raw_segment_time, "-st")
  return max(1, int(round(segment_time_seconds)))


def validate_arguments(total_duration_seconds: int, segment_time_seconds: int, segment_wrap: int | None) -> None:
  """Validate parsed CLI arguments."""
  if total_duration_seconds <= 0:
    raise ValueError("-t must be greater than 0 seconds")

  if segment_wrap is not None and segment_wrap <= 0:
    raise ValueError("-sw must be an integer greater than 0")

  if segment_time_seconds <= 0:
    raise ValueError("-st must resolve to a value greater than 0 seconds")

  if segment_time_seconds >= total_duration_seconds:
    raise ValueError("segment_time_seconds must be less than total_duration_seconds")


async def run_ffmpeg_for_source(
  source: Source,
  total_duration_seconds: int,
  segment_time_seconds: int,
  segment_wrap: int | None,
  base_output_dir: Path,
) -> tuple[Source, int]:
  """Run one ffmpeg process for a single source."""
  source_output_dir: Path = base_output_dir / f"pipeline_{source.name}"
  source_output_dir.mkdir(parents=True, exist_ok=True)
  log_path: Path = source_output_dir / "logs.txt"

  command: list[str] = [
    "ffmpeg",
    "-nostdin",
    "-reconnect", "1",
    "-reconnect_streamed", "1",
    "-reconnect_on_http_error", "4xx,5xx",
    "-reconnect_delay_max", "5",
    "-t", str(total_duration_seconds),
    "-i", source.url,
    "-vn",
    
    "-map", "0:a:0",
    "-c:a", "pcm_s16le",
    "-f", "segment",
    "-segment_time", str(segment_time_seconds),
    "-segment_format", "wav",
    "-reset_timestamps", "1",
    "-segment_start_number", "0",
  ]

  if segment_wrap is not None:
    command.extend(["-segment_wrap", str(segment_wrap)])

  command.extend(
    [
      f"{source.source_id}_out_%05d.wav",
      # Full output (same bounded duration)
      "-map", "0:a:0",
      "-c:a", "pcm_s16le",
      f"{source.source_id}_full.wav",
    ]
  )

  process: asyncio.subprocess.Process | None = None
  with log_path.open("w", encoding="utf-8") as log_file:
    try:
      process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(source_output_dir),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=log_file,
      )
      return_code: int = await process.wait()
    except asyncio.CancelledError:
      if process is not None and process.returncode is None:
        process.terminate()
        try:
          await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
          process.kill()
          await process.wait()
      raise

  return source, return_code


async def async_main() -> int:
  """Parse arguments and execute ffmpeg jobs in parallel."""
  args: argparse.Namespace = parse_args()
  script_dir: Path = Path(__file__).resolve().parent

  total_duration_float: float = parse_time_value(args.total_duration, "-t")
  total_duration_seconds: int = max(1, int(round(total_duration_float)))
  segment_time_seconds: int = compute_segment_time_seconds(total_duration_seconds, args.segment_time)

  validate_arguments(total_duration_seconds, segment_time_seconds, args.segment_wrap)

  selected_sources: list[Source] = build_sources_from_urls(args.input_urls)

  if not selected_sources:
    raise ValueError("No sources selected")

  output_root: Path = script_dir
  tasks: list[asyncio.Task[tuple[Source, int]]] = [
    asyncio.create_task(
      run_ffmpeg_for_source(
        source=source,
        total_duration_seconds=total_duration_seconds,
        segment_time_seconds=segment_time_seconds,
        segment_wrap=args.segment_wrap,
        base_output_dir=output_root,
      )
    )
    for source in selected_sources
  ]

  timeout_seconds: int = total_duration_seconds + EXCEDING_TIME_BUFFER_SECONDS
  try:
    results: list[tuple[Source, int]] = await asyncio.wait_for(
      asyncio.gather(*tasks),
      timeout=timeout_seconds,
    )
  except asyncio.TimeoutError:
    print(
      f"[ERROR] Timeout reached ({timeout_seconds}s). Stopping unfinished ffmpeg processes.",
      file=sys.stderr,
    )
    for task in tasks:
      if not task.done():
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    return 1

  failures: list[tuple[Source, int]] = [result for result in results if result[1] != 0]

  for source, return_code in results:
    if return_code == 0:
      print(f"[OK] Source '{source.source_id}' ({source.name}) finished successfully")

  if failures:
    for source, return_code in failures:
      print(
        f"[ERROR] Source '{source.source_id}' ({source.name}) failed with code {return_code}",
        file=sys.stderr,
      )
    return 1

  return 0

if __name__ == "__main__":
  try:
    s_datetime: datetime = datetime.now()
    script_dir: Path = Path(__file__).resolve().parent
    start_datetime_path: Path = script_dir / "execution_starting_date.txt"
    start_datetime_path.write_text(s_datetime.strftime("%d/%m/%Y:%H:%M:%S"), encoding="utf-8")
    exit_code: int = asyncio.run(async_main())
  except ValueError as error:
    print(f"Argument error: {error}", file=sys.stderr)
    sys.exit(2)
  except KeyboardInterrupt:
    print("Interrupted by user", file=sys.stderr)
    sys.exit(130)
  sys.exit(exit_code)
