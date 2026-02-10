#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time


def resolve_vosk_transcriber() -> str:
  """Resolve the vosk-transcriber executable with virtualenv fallback."""
  script_dir = Path(__file__).resolve().parent
  repo_root = script_dir.parent

  interpreter_candidate = Path(sys.executable).resolve().parent / "vosk-transcriber"
  if interpreter_candidate.exists():
    return str(interpreter_candidate)

  for env_root in (script_dir, repo_root):
    for env_name in (".venv", "venv"):
      local_candidate = env_root / env_name / "bin" / "vosk-transcriber"
      if local_candidate.exists():
        return str(local_candidate)

  from_path: str | None = shutil.which("vosk-transcriber")
  if from_path is not None:
    return from_path

  current_virtual_env: str | None = os.environ.get("VIRTUAL_ENV")
  if current_virtual_env is not None:
    env_candidate = Path(current_virtual_env) / "bin" / "vosk-transcriber"
    if env_candidate.exists():
      return str(env_candidate)

  raise FileNotFoundError(
    "Could not find 'vosk-transcriber'. Activate your virtual environment "
    "or install it in .venv/venv."
  )


def execute(command_path: str) -> str:
  """Run vosk transcription command once."""
  script_dir = Path(__file__).resolve().parent
  input_file = script_dir / "experiment_fixed.wav"
  output_file = script_dir / "_vosk_benchmark_output.txt"

  command: list[str] = [
    command_path,
    "--model-name",
    "vosk-model-small-es-0.42",
    "--input",
    str(input_file),
    "--output",
    str(output_file),
    "--log-level",
    "ERROR",
    "--output-type",
    "txt"
  ]
  try:
    subprocess.run(command, check=True, capture_output=True, text=True, cwd=script_dir)
  except subprocess.CalledProcessError as exc:
    stderr = (exc.stderr or "").strip()
    raise RuntimeError(
      f"vosk-transcriber failed with exit code {exc.returncode}: {stderr}"
    ) from exc

  if output_file.exists():
    return output_file.read_text(encoding="utf-8")
  return ""


def main() -> None:
  """Benchmark vosk transcription runtime across repeated runs."""
  script_dir = Path(__file__).resolve().parent
  output_file = script_dir / "_vosk_benchmark_output.txt"
  command_path = resolve_vosk_transcriber()
  times: list[float] = []

  # Load models
  execute(command_path)

  # warm-up
  for _ in range(2):
    execute(command_path)

  # measured runs
  for _ in range(6):
    start = time.perf_counter()
    execute(command_path)
    end = time.perf_counter()
    times.append(end - start)

  print("avg:", statistics.mean(times))
  print("min:", min(times))
  print("std:", statistics.stdev(times))

  if output_file.exists():
    output_file.unlink()


if __name__ == "__main__":
  main()
