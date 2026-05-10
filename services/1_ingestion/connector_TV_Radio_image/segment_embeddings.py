import argparse
from sentence_transformers import SentenceTransformer
import ast
import json
import math
import re
import sys
import uuid
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray


# Default: k = 6, min_gap_units = 8, peak_threshold = 0.25
K: int = 6
MIN_GAP_UNITS: int = 8
PEAK_THRESHOLD: float = 0.25
OUTPUT_DIR: Path = Path("/outputs/common")
SEGMENT_PRESETS: dict[str, dict[str, float]] = {
  "short": {
    "k": 3,
    "min_gap_units": 4,
    "peak_threshold": 0.16,
  },
  "medium": {
    "k": 5,
    "min_gap_units": 8,
    "peak_threshold": 0.22,
  },
  "long": {
    "k": 8,
    "min_gap_units": 12,
    "peak_threshold": 0.18,
  },
}


class Unit(TypedDict):
  """Represents one timestamped transcription unit."""
  s: float
  e: float
  text: str


class Story(TypedDict):
  """Represents one segmented story chunk."""
  story_id: int
  s: float
  e: float
  text: str


class PipelineMetadata(TypedDict):
  """Represents metadata stored in pipeline metadata.txt files."""
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


def load_transcription(file_path: str) -> dict[str, str]:
  """Load transcription entries from the merged transcription file."""
  with open(file_path, "r") as file:
    raw_data: str = file.read()
    try:
      parsed_data: dict[str, dict[str, str]] = json.loads(raw_data)
    except json.JSONDecodeError:
      parsed_data = ast.literal_eval(raw_data)
    return parsed_data["transcription"]


def parse_time_token(token: str) -> float:
  """Parse a single time token to seconds."""
  clean_token: str = re.sub(r"[^0-9:.,]", "", token.strip()).replace(",", ".")
  if not clean_token:
    raise ValueError(f"Could not parse time token: {token}")
  parts: list[str] = clean_token.split(":")

  if len(parts) == 3:
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return (hours * 3600.0) + (minutes * 60.0) + seconds
  if len(parts) == 2:
    minutes = float(parts[0])
    seconds = float(parts[1])
    return (minutes * 60.0) + seconds
  return float(parts[0])


def parse_range(ts_str: str) -> tuple[float, float]:
  """Parse a timestamp range string into start/end seconds."""
  full_time_matches: list[str] = re.findall(r"\d{1,2}:\d{2}:\d{2}(?:[\.,]\d+)?", ts_str)
  if len(full_time_matches) >= 2:
    return parse_time_token(full_time_matches[0]), parse_time_token(full_time_matches[1])

  generic_time_matches: list[str] = re.findall(r"\d{1,2}:\d{2}(?:[\.,]\d+)?|\d+(?:[\.,]\d+)?", ts_str)
  if len(generic_time_matches) >= 2:
    return parse_time_token(generic_time_matches[0]), parse_time_token(generic_time_matches[1])

  raise ValueError(f"Could not parse timestamp range: {ts_str}")


def embed_texts(model: SentenceTransformer, texts: list[str]) -> NDArray[np.float32]:
  """Embed all texts into a matrix of vectors."""
  embeddings: Any = model.encode(texts, convert_to_numpy=True)
  return np.asarray(embeddings, dtype=np.float32)


def normalize(vec: NDArray[np.float32]) -> NDArray[np.float32]:
  """Return L2-normalized vector; keep zero vector unchanged."""
  norm: float = float(np.linalg.norm(vec))
  if norm == 0.0:
    return vec
  return vec / norm


def cosine_sim(a: NDArray[np.float32], b: NDArray[np.float32]) -> float:
  """Compute cosine similarity via normalized dot product."""
  return float(np.dot(normalize(a), normalize(b)))


def build_units(transcription: dict[str, str]) -> list[Unit]:
  """Convert transcription dict to sorted units with numeric ranges."""
  units: list[Unit] = []
  for ts_str, text in transcription.items():
    start_seconds, end_seconds = parse_range(ts_str)
    units.append({"s": start_seconds, "e": end_seconds, "text": text})

  units.sort(key=lambda unit: unit["s"])
  return units


def compute_embeddings(model: SentenceTransformer, units: list[Unit]) -> NDArray[np.float32]:
  """Compute one normalized embedding vector for each unit."""
  texts: list[str] = [unit["text"] for unit in units]
  embeddings: NDArray[np.float32] = embed_texts(model, texts)

  for index in range(embeddings.shape[0]):
    embeddings[index] = normalize(embeddings[index])

  return embeddings


def compute_boundary_scores(embeddings: NDArray[np.float32], k: int) -> list[float]:
  """Compute boundary score per split index using left/right windows."""
  total_units: int = int(embeddings.shape[0])
  scores: list[float] = [math.nan for _ in range(max(0, total_units - 1))]

  for boundary_index in range(total_units - 1):
    left_start = boundary_index - k + 1
    left_end = boundary_index
    right_start = boundary_index + 1
    right_end = boundary_index + k

    if left_start < 0 or right_end >= total_units:
      continue

    left_window: NDArray[np.float32] = embeddings[left_start:left_end + 1]
    right_window: NDArray[np.float32] = embeddings[right_start:right_end + 1]

    left_mean_raw: NDArray[np.float32] = np.asarray(np.mean(left_window, axis=0), dtype=np.float32)
    right_mean_raw: NDArray[np.float32] = np.asarray(np.mean(right_window, axis=0), dtype=np.float32)
    left_mean: NDArray[np.float32] = normalize(left_mean_raw)
    right_mean: NDArray[np.float32] = normalize(right_mean_raw)

    similarity: float = cosine_sim(left_mean, right_mean)
    scores[boundary_index] = 1.0 - similarity

  return scores


def pick_peak_candidates(scores: list[float], peak_threshold: float) -> list[int]:
  """Pick local-maximum boundary candidates over threshold."""
  candidates: list[int] = []
  for index in range(1, len(scores) - 1):
    current = scores[index]
    previous = scores[index - 1]
    next_value = scores[index + 1]

    if math.isnan(current) or math.isnan(previous) or math.isnan(next_value):
      continue
    if current > peak_threshold and current > previous and current >= next_value:
      candidates.append(index)

  return candidates


def enforce_min_gap(candidates: list[int], scores: list[float], min_gap_units: int) -> list[int]:
  """Keep strongest boundaries while enforcing minimum unit distance."""
  sorted_candidates: list[int] = sorted(candidates, key=lambda index: scores[index], reverse=True)
  kept: list[int] = []

  for candidate in sorted_candidates:
    if not kept:
      kept.append(candidate)
      continue

    is_far_enough: bool = all(abs(candidate - existing) >= min_gap_units for existing in kept)
    if is_far_enough:
      kept.append(candidate)

  kept.sort()
  return kept


def build_story_chunks(units: list[Unit], boundaries: list[int]) -> list[Story]:
  """Build final story chunks using selected boundaries."""
  stories: list[Story] = []
  total_units: int = len(units)
  start_index = 0
  story_id = 0

  for boundary in boundaries:
    end_index = boundary
    story_units = units[start_index:end_index + 1]
    if story_units:
      stories.append(
        {
          "story_id": story_id,
          "s": story_units[0]["s"],
          "e": story_units[-1]["e"],
          "text": " ".join(unit["text"] for unit in story_units),
        }
      )
      story_id += 1
    start_index = boundary + 1

  if start_index < total_units:
    story_units = units[start_index:total_units]
    stories.append(
      {
        "story_id": story_id,
        "s": story_units[0]["s"],
        "e": story_units[-1]["e"],
        "text": " ".join(unit["text"] for unit in story_units),
      }
    )

  return stories


def segment_stories(
  transcription: dict[str, str],
  model: SentenceTransformer,
  k: int,
  min_gap_units: int,
  peak_threshold: float,
) -> tuple[list[Story], list[float], list[int]]:
  """Run full boundary-based story segmentation pipeline."""
  units: list[Unit] = build_units(transcription)
  embeddings: NDArray[np.float32] = compute_embeddings(model, units)
  scores: list[float] = compute_boundary_scores(embeddings, k)
  candidates: list[int] = pick_peak_candidates(scores, peak_threshold)
  boundaries: list[int] = enforce_min_gap(candidates, scores, min_gap_units)
  stories: list[Story] = build_story_chunks(units, boundaries)
  return stories, scores, boundaries


def save_json(payload: Any, output_path: str) -> None:
  """Save JSON payload to file with indentation."""
  with open(output_path, "w") as file:
    json.dump(payload, file, indent=2, ensure_ascii=False)


def iter_transcription_files(base_dir: Path) -> list[Path]:
  """Find all merged transcription files inside pipeline directories."""
  return sorted(base_dir.glob("pipeline_*/*_transcription_merged.json"))


def load_pipeline_metadata(metadata_path: Path) -> PipelineMetadata:
  """Load pipeline metadata.txt into a dictionary."""
  metadata: dict[str, str] = {}
  for line in metadata_path.read_text(encoding="utf-8").splitlines():
    if not line.strip() or "=" not in line:
      continue
    key, value = line.split("=", 1)
    metadata[key.strip()] = value.strip()

  return {
    "airflow_dag_id": metadata.get("airflow_dag_id", ""),
    "extracted_at": metadata.get("extracted_at", ""),
    "airflow_run_id": metadata.get("airflow_run_id", ""),
    "connector_id": metadata.get("connector_id", ""),
    "connector_name": metadata.get("connector_name", ""),
    "source_url": metadata.get("source_url", ""),
    "source_name": metadata.get("source_name", ""),
    "source_type": metadata.get("source_type", ""),
    "language": metadata.get("language", ""),
    "country": metadata.get("country", ""),
    "source_tags": metadata.get("source_tags", ""),
  }


def build_story_payload(
  metadata: PipelineMetadata,
  story: Story,
  t: str | None,
  nt: str | None,
  m: str | None,
  k: int,
  min_gap_units: int,
  peak_threshold: float,
  news_length: str | None,
) -> dict[str, Any]:
  """Build one output payload for a segmented news item."""
  news_id: str = uuid.uuid4().hex
  start: float = story["s"]
  end: float = story["e"]
  duration: float = max(0.0, end - start)

  return {
    "id": news_id,
    "source_url": metadata["source_url"],
    "airflow_dag_id": metadata["airflow_dag_id"],
    "extracted_at": metadata["extracted_at"],
    "airflow_run_id": metadata["airflow_run_id"],
    "connector_id": metadata["connector_id"],
    "connector_name": metadata["connector_name"],
    "source_name": metadata["source_name"],
    "source_type": metadata["source_type"],
    "language": metadata["language"],
    "country": metadata["country"],
    "source_tags": metadata["source_tags"],
    "content": story["text"],
    "other": {
      "start": start,
      "end": end,
      "duration": duration,
      "parameters": {
        "t": t,
        "nt": nt,
        "m": m,
        "k": k,
        "mgu": min_gap_units,
        "pt": peak_threshold,
        "news_length": news_length,
      },
    },
  }


def build_outputs_dir(script_dir: Path) -> Path:
  """Resolve and create the configured outputs directory."""
  #output_dir: Path = OUTPUT_DIR if OUTPUT_DIR.is_absolute() else (script_dir / OUTPUT_DIR)
  output_dir = OUTPUT_DIR
  output_dir.mkdir(parents=True, exist_ok=True)
  return output_dir


def save_story_payloads(
  output_dir: Path,
  metadata: PipelineMetadata,
  stories: list[Story],
  t: str | None,
  nt: str | None,
  m: str | None,
  k: int,
  min_gap_units: int,
  peak_threshold: float,
  news_length: str | None,
) -> list[Path]:
  """Write one JSON file per segmented story into the outputs directory."""
  output_paths: list[Path] = []
  for story in stories:
    payload: dict[str, Any] = build_story_payload(
      metadata=metadata,
      story=story,
      t=t,
      nt=nt,
      m=m,
      k=k,
      min_gap_units=min_gap_units,
      peak_threshold=peak_threshold,
      news_length=news_length,
    )
    output_path: Path = output_dir / f"{metadata['airflow_dag_id']}_{metadata['airflow_run_id']}_{payload['id']}.json"
    save_json(payload, str(output_path))
    output_paths.append(output_path)
  return output_paths


def format_output_path(path: Path, script_dir: Path) -> str:
  """Return a readable path for console output."""
  try:
    return str(path.relative_to(script_dir))
  except ValueError:
    return str(path)


def parse_args() -> argparse.Namespace:
  """Parse optional CLI overrides for segmentation parameters."""
  parser: argparse.ArgumentParser = argparse.ArgumentParser(
    description="Segment merged transcriptions into story chunks"
  )
  parser.add_argument(
    "-t",
    dest="t",
    help="Pass-through parameter stored in output payloads.",
  )
  parser.add_argument(
    "-nt",
    dest="nt",
    help="Pass-through parameter stored in output payloads.",
  )
  parser.add_argument(
    "-m",
    dest="m",
    help="Pass-through parameter stored in output payloads.",
  )
  parser.add_argument(
    "-news_length",
    choices=sorted(SEGMENT_PRESETS.keys()),
    dest="news_length",
    help="Use a preset tuned for short, medium, or long news items.",
  )
  parser.add_argument(
    "-k",
    type=int,
    default=K,
    dest="k",
    help="Boundary window size.",
  )
  parser.add_argument(
    "-mgu",
    type=int,
    default=MIN_GAP_UNITS,
    dest="min_gap_units",
    help="Minimum gap between accepted boundaries in units.",
  )
  parser.add_argument(
    "-pt",
    type=float,
    default=PEAK_THRESHOLD,
    dest="peak_threshold",
    help="Minimum score for a boundary peak candidate.",
  )
  return parser.parse_args()


def resolve_segmentation_parameters(
  k: int,
  min_gap_units: int,
  peak_threshold: float,
  news_length: str | None = None,
) -> tuple[int, int, float]:
  """Resolve manual or preset segmentation parameters."""
  if news_length is None:
    return k, min_gap_units, peak_threshold

  preset: dict[str, float] = SEGMENT_PRESETS[news_length]
  return int(preset["k"]), int(preset["min_gap_units"]), float(preset["peak_threshold"])


def validate_parameters(k: int, min_gap_units: int, peak_threshold: float) -> None:
  """Validate segmentation parameter values."""
  if k <= 0:
    raise ValueError("-k must be greater than 0")
  if min_gap_units <= 0:
    raise ValueError("-mgu must be greater than 0")
  if peak_threshold < 0.0:
    raise ValueError("-pt must be greater than or equal to 0")


def has_manual_segmentation_flags(argv: list[str]) -> bool:
  """Return whether manual segmentation flags were provided explicitly."""
  manual_flags: tuple[str, ...] = ("-k", "-mgu", "-pt")
  return any(flag in argv for flag in manual_flags)


def main(
  t: str | None = None,
  nt: str | None = None,
  m: str | None = None,
  k: int = K,
  min_gap_units: int = MIN_GAP_UNITS,
  peak_threshold: float = PEAK_THRESHOLD,
  news_length: str | None = None,
) -> None:
  """Segment all merged transcriptions in pipeline directories."""
  k, min_gap_units, peak_threshold = resolve_segmentation_parameters(
    k=k,
    min_gap_units=min_gap_units,
    peak_threshold=peak_threshold,
    news_length=news_length,
  )
  validate_parameters(k, min_gap_units, peak_threshold)
  model = SentenceTransformer("BAAI/bge-m3")

  script_dir: Path = Path(__file__).resolve().parent
  output_dir: Path = build_outputs_dir(script_dir)
  transcription_files: list[Path] = iter_transcription_files(script_dir)

  for transcription_file in transcription_files:
    metadata_path: Path = transcription_file.parent / "metadata.txt"
    metadata: PipelineMetadata = load_pipeline_metadata(metadata_path)
    transcription = load_transcription(str(transcription_file))
    stories, _, _ = segment_stories(
      transcription=transcription,
      model=model,
      k=k,
      min_gap_units=min_gap_units,
      peak_threshold=peak_threshold,
    )
    output_paths: list[Path] = save_story_payloads(
      output_dir=output_dir,
      metadata=metadata,
      stories=stories,
      t=t,
      nt=nt,
      m=m,
      k=k,
      min_gap_units=min_gap_units,
      peak_threshold=peak_threshold,
      news_length=news_length,
    )

    print(f"Processed: {transcription_file.relative_to(script_dir)}")
    for output_path in output_paths:
      print(f"Saved story JSON to: {format_output_path(output_path, script_dir)}")


if __name__ == "__main__":
  args: argparse.Namespace = parse_args()
  if args.news_length is not None and has_manual_segmentation_flags(sys.argv[1:]):
    raise ValueError("-news_length cannot be combined with -k, -mgu, or -pt")
  main(
    t=args.t,
    nt=args.nt,
    m=args.m,
    k=args.k,
    min_gap_units=args.min_gap_units,
    peak_threshold=args.peak_threshold,
    news_length=args.news_length,
  )
