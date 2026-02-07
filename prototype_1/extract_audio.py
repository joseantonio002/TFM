import asyncio
import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TIME_PATTERN: re.Pattern[str] = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)$")


@dataclass(frozen=True)
class Source:
  source_id: str
  name: str
  url: str


def parse_time_value(raw_value: str, argument_name: str) -> float:
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
  parser: argparse.ArgumentParser = argparse.ArgumentParser(
    description="Extract segmented audio from streaming sources in parallel"
  )
  parser.add_argument(
    "-i",
    nargs="+",
    dest="input_ids",
    help="Source IDs separated by spaces. If omitted, all sources are used.",
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


def load_sources(file_path: Path) -> dict[str, Any]:
  with file_path.open("r", encoding="utf-8") as source_file:
    data: Any = json.load(source_file)
  if not isinstance(data, dict):
    raise ValueError("sources.json must contain an object keyed by source IDs")
  return data


def build_source(source_id: str, source_data: Any) -> Source:
  if not isinstance(source_data, dict):
    raise ValueError(f"Source '{source_id}' must be an object")
  url: Any = source_data.get("url")
  if not isinstance(url, str) or not url.strip():
    raise ValueError(f"Source '{source_id}' has an invalid or missing 'url'")
  raw_name: Any = source_data.get("name")
  name: str = str(raw_name).strip() if raw_name is not None else ""
  if not name:
    name = source_id
  return Source(source_id=source_id, name=name, url=url.strip())


def select_sources(all_sources: dict[str, Any], selected_ids: list[str] | None) -> list[Source]:
  ordered_ids: list[str]
  if selected_ids is None:
    ordered_ids = list(all_sources.keys())
  else:
    ordered_ids = selected_ids
    missing_ids: list[str] = [source_id for source_id in ordered_ids if source_id not in all_sources]
    if missing_ids:
      missing_display: str = ", ".join(missing_ids)
      raise ValueError(f"Source IDs not found in sources.json: {missing_display}")

  return [build_source(source_id, all_sources[source_id]) for source_id in ordered_ids]


def compute_segment_time_seconds(total_duration_seconds: int, raw_segment_time: str | None) -> int:
  if raw_segment_time is None:
    computed: int = int(round(total_duration_seconds * 0.2))
    return max(1, computed)

  segment_time_seconds: float = parse_time_value(raw_segment_time, "-st")
  return max(1, int(round(segment_time_seconds)))


def validate_arguments(total_duration_seconds: int, segment_time_seconds: int, segment_wrap: int | None) -> None:
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
  source_output_dir: Path = base_output_dir / source.name
  source_output_dir.mkdir(parents=True, exist_ok=True)
  log_path: Path = source_output_dir / "logs.txt"

  command: list[str] = [
    "ffmpeg",
    "-reconnect",
    "1",
    "-reconnect_streamed",
    "1",
    "-reconnect_on_http_error",
    "4xx,5xx",
    "-reconnect_delay_max",
    "5",
    "-nostdin",
    "-i",
    source.url,
    "-vn",
    "-t",
    str(total_duration_seconds),
    "-c:a",
    "copy",
    "-f",
    "segment",
    "-segment_time",
    str(segment_time_seconds),
  ]

  if segment_wrap is not None:
    command.extend(["-segment_wrap", str(segment_wrap)])

  command.extend(["-reset_timestamps", "1", "out_%05d.m4a"])

  #print(command)

  with log_path.open("w", encoding="utf-8") as log_file:
    process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
      *command,
      cwd=str(source_output_dir),
      stdout=asyncio.subprocess.DEVNULL,
      stderr=log_file,
    )
    return_code: int = await process.wait()

  return source, return_code


async def async_main() -> int:
  args: argparse.Namespace = parse_args()
  script_dir: Path = Path(__file__).resolve().parent
  sources_path: Path = script_dir / "sources.json"

  total_duration_float: float = parse_time_value(args.total_duration, "-t")
  total_duration_seconds: int = max(1, int(round(total_duration_float)))
  segment_time_seconds: int = compute_segment_time_seconds(total_duration_seconds, args.segment_time)

  validate_arguments(total_duration_seconds, segment_time_seconds, args.segment_wrap)

  sources_data: dict[str, Any] = load_sources(sources_path)
  selected_sources: list[Source] = select_sources(sources_data, args.input_ids)

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

  results: list[tuple[Source, int]] = await asyncio.gather(*tasks)
  failures: list[tuple[Source, int]] = [result for result in results if result[1] != 0]

  if failures:
    for source, return_code in failures:
      print(
        f"[ERROR] Source '{source.source_id}' ({source.name}) failed with code {return_code}",
        file=sys.stderr,
      )
    return 1

  for source, _ in results:
    print(f"[OK] Source '{source.source_id}' ({source.name}) finished successfully")
  return 0




if __name__ == "__main__":
  try:
    exit_code: int = asyncio.run(async_main())
  except ValueError as error:
    print(f"Argument error: {error}", file=sys.stderr)
    sys.exit(2)
  except KeyboardInterrupt:
    print("Interrupted by user", file=sys.stderr)
    sys.exit(130)
  sys.exit(exit_code)
