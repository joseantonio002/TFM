import asyncio
import argparse
import os
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


@dataclass(frozen=True)
class SourceMetadata:
  airflow_dag_id: str
  extracted_at: str
  connector_id: str
  connector_name: str
  source_url: str
  source_name: str
  source_type: str
  language: str
  country: str
  source_tags: str


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


def split_source_metadata(raw_value: str, input_count: int, variable_name: str) -> list[str]:
  """Split a source-scoped environment variable into one value per input source."""
  if input_count == 0:
    return []

  values: list[str] = raw_value.split("::") if raw_value else [""] * input_count
  if len(values) != input_count:
    raise ValueError(
      f"{variable_name} must contain exactly {input_count} values separated by '::'"
    )
  return values


def load_metadata_from_environment(input_count: int) -> list[SourceMetadata]:
  """Load global and source-scoped metadata from environment variables."""
  airflow_dag_id: str = os.environ.get("AIRFLOW_DAG_ID", "")
  extracted_at: str = os.environ.get("EXTRACTED_AT", "")
  connector_id: str = os.environ.get("CONNECTOR_ID", "")
  connector_name: str = os.environ.get("CONNECTOR_NAME", "")

  source_names: list[str] = split_source_metadata(
    os.environ.get("SOURCE_NAME", ""),
    input_count,
    "SOURCE_NAME",
  )
  source_types: list[str] = split_source_metadata(
    os.environ.get("SOURCE_TYPE", ""),
    input_count,
    "SOURCE_TYPE",
  )
  languages: list[str] = split_source_metadata(
    os.environ.get("LANGUAGE", ""),
    input_count,
    "LANGUAGE",
  )
  countries: list[str] = split_source_metadata(
    os.environ.get("COUNTRY", ""),
    input_count,
    "COUNTRY",
  )
  source_tags: list[str] = split_source_metadata(
    os.environ.get("SOURCE_TAGS", ""),
    input_count,
    "SOURCE_TAGS",
  )

  return [
    SourceMetadata(
      airflow_dag_id=airflow_dag_id,
      extracted_at=extracted_at,
      connector_id=connector_id,
      connector_name=connector_name,
      source_url="",
      source_name=source_names[index],
      source_type=source_types[index],
      language=languages[index],
      country=countries[index],
      source_tags=source_tags[index],
    )
    for index in range(input_count)
  ]


def write_metadata_file(output_dir: Path, metadata: SourceMetadata) -> None:
  """Write pipeline metadata as key=value lines inside the output directory."""
  metadata_path: Path = output_dir / "metadata.txt"
  metadata_lines: list[str] = [
    f"airflow_dag_id={metadata.airflow_dag_id}",
    f"extracted_at={metadata.extracted_at}",
    f"connector_id={metadata.connector_id}",
    f"connector_name={metadata.connector_name}",
    f"source_url={metadata.source_url}",
    f"source_name={metadata.source_name}",
    f"source_type={metadata.source_type}",
    f"language={metadata.language}",
    f"country={metadata.country}",
    f"source_tags={metadata.source_tags}",
  ]
  metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")


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
  metadata: SourceMetadata,
  total_duration_seconds: int,
  segment_time_seconds: int,
  segment_wrap: int | None,
  base_output_dir: Path,
) -> tuple[Source, int]:
  """Run one ffmpeg process for a single source."""
  source_output_dir: Path = base_output_dir / f"pipeline_{source.name}"
  source_output_dir.mkdir(parents=True, exist_ok=True)
  write_metadata_file(
    source_output_dir,
    SourceMetadata(
      airflow_dag_id=metadata.airflow_dag_id,
      extracted_at=metadata.extracted_at,
      connector_id=metadata.connector_id,
      connector_name=metadata.connector_name,
      source_url=source.url,
      source_name=metadata.source_name,
      source_type=metadata.source_type,
      language=metadata.language,
      country=metadata.country,
      source_tags=metadata.source_tags,
    ),
  )
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
  return await run_extraction(
    input_urls=list(args.input_urls),
    total_duration=args.total_duration,
    segment_wrap=args.segment_wrap,
    segment_time=args.segment_time,
  )


async def run_extraction(
  input_urls: list[str],
  total_duration: str,
  segment_wrap: int | None = None,
  segment_time: str | None = None,
) -> int:
  """Execute ffmpeg extraction jobs from explicit arguments."""
  script_dir: Path = Path(__file__).resolve().parent

  total_duration_float: float = parse_time_value(total_duration, "-t")
  total_duration_seconds: int = max(1, int(round(total_duration_float)))
  segment_time_seconds: int = compute_segment_time_seconds(total_duration_seconds, segment_time)

  validate_arguments(total_duration_seconds, segment_time_seconds, segment_wrap)

  selected_sources: list[Source] = build_sources_from_urls(input_urls)
  selected_metadata: list[SourceMetadata] = load_metadata_from_environment(len(selected_sources))

  if not selected_sources:
    raise ValueError("No sources selected")

  output_root: Path = script_dir
  tasks: list[asyncio.Task[tuple[Source, int]]] = [
    asyncio.create_task(
      run_ffmpeg_for_source(
        source=source,
        metadata=selected_metadata[index],
        total_duration_seconds=total_duration_seconds,
        segment_time_seconds=segment_time_seconds,
        segment_wrap=segment_wrap,
        base_output_dir=output_root,
      )
    )
    for index, source in enumerate(selected_sources)
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


def main(
  input_urls: list[str],
  total_duration: str,
  segment_wrap: int | None = None,
  segment_time: str | None = None,
) -> None:
  """Run audio extraction and persist the execution start time."""
  s_datetime: datetime = datetime.now()
  script_dir: Path = Path(__file__).resolve().parent
  start_datetime_path: Path = script_dir / "execution_starting_date.txt"
  start_datetime_path.write_text(s_datetime.strftime("%d/%m/%Y:%H:%M:%S"), encoding="utf-8")

  exit_code: int = asyncio.run(
    run_extraction(
      input_urls=input_urls,
      total_duration=total_duration,
      segment_wrap=segment_wrap,
      segment_time=segment_time,
    )
  )
  if exit_code != 0:
    raise RuntimeError(f"extract_audio failed with exit code {exit_code}")

if __name__ == "__main__":
  parsed_args: argparse.Namespace = parse_args()
  main(
    input_urls=list(parsed_args.input_urls),
    total_duration=parsed_args.total_duration,
    segment_wrap=parsed_args.segment_wrap,
    segment_time=parsed_args.segment_time,
  )
