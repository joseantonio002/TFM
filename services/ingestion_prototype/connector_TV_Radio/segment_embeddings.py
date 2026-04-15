from sentence_transformers import SentenceTransformer
import ast
import importlib
import json
import math
import re
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray


# Default: k = 6, min_gap_units = 8, peak_threshold = 0.25
K: int = 6
MIN_GAP_UNITS: int = 8
PEAK_THRESHOLD: float = 0.25


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


def plot_scores(scores: list[float], boundaries: list[int], output_path: str) -> None:
  """Save a line graph of boundary scores and selected boundaries."""
  plt: Any = importlib.import_module("matplotlib.pyplot")
  x_values: list[int] = list(range(len(scores)))
  y_values: list[float] = [value if not math.isnan(value) else 0.0 for value in scores]

  plt.figure(figsize=(14, 6))
  plt.plot(x_values, y_values, marker="o", linewidth=1.5, label="boundary score")

  if boundaries:
    boundary_values: list[float] = [y_values[index] for index in boundaries]
    plt.scatter(boundaries, boundary_values, color="red", s=50, label="selected boundaries", zorder=3)

  plt.title("Boundary Scores for Story Segmentation")
  plt.xlabel("Boundary Index (between unit i and i+1)")
  plt.ylabel("Score (1 - cosine similarity)")
  plt.grid(True, linestyle="--", alpha=0.4)
  plt.legend()
  plt.tight_layout()
  plt.savefig(output_path, dpi=200)
  plt.close()


def iter_transcription_files(base_dir: Path) -> list[Path]:
  """Find all merged transcription files inside pipeline directories."""
  return sorted(base_dir.glob("pipeline_*/*_transcription_merged.json"))


def build_segmented_output_path(transcription_path: Path) -> Path:
  """Build output path by appending _segmented to file stem."""
  return transcription_path.with_name(f"{transcription_path.stem}_segmented.json")


def main() -> None:
  """Segment all merged transcriptions in pipeline directories."""
  model = SentenceTransformer("BAAI/bge-m3")

  k = K
  min_gap_units = MIN_GAP_UNITS
  peak_threshold = PEAK_THRESHOLD

  script_dir: Path = Path(__file__).resolve().parent
  transcription_files: list[Path] = iter_transcription_files(script_dir)

  for transcription_file in transcription_files:
    transcription = load_transcription(str(transcription_file))
    stories, scores, boundaries = segment_stories(
      transcription=transcription,
      model=model,
      k=k,
      min_gap_units=min_gap_units,
      peak_threshold=peak_threshold,
    )

    segmented_output_path: Path = build_segmented_output_path(transcription_file)
    graph_output_path: Path = transcription_file.with_name(f"{transcription_file.stem}_scores.png")

    save_json(stories, str(segmented_output_path))
    plot_scores(scores, boundaries, str(graph_output_path))

    print(f"Processed: {transcription_file.relative_to(script_dir)}")
    print(f"Saved segmented stories to: {segmented_output_path.relative_to(script_dir)}")
    print(f"Saved boundary score graph to: {graph_output_path.relative_to(script_dir)}")


if __name__ == "__main__":
  main()
