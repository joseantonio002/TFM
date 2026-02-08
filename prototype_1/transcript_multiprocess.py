import subprocess
import time
from multiprocessing import Process
from pathlib import Path


def get_input_files(base_dir: Path) -> list[Path]:
  """Return final WAV files from pipeline directories."""
  return sorted(base_dir.glob("pipeline_*/*_final.wav"), key=lambda path: path.name)


def build_command(input_file: Path, project_root: Path) -> list[str]:
  """Build whisper-cli command for one input file."""
  output_prefix: Path = input_file.parent / f"{input_file.parent.name}_transcript.txt"
  return [
    str(project_root / "whisper.cpp" / "build" / "bin" / "whisper-cli"),
    "-m",
    str(project_root / "whisper.cpp" / "models" / "ggml-tiny.bin"),
    "-l",
    "es",
    "-otxt",
    "-of",
    str(output_prefix),
    "-f",
    str(input_file),
  ]


def run_transcription(input_file: Path, project_root: Path) -> None:
  """Run one whisper transcription process in a child process."""
  command: list[str] = build_command(input_file, project_root)
  subprocess.run(command, cwd=input_file.parent)


def main() -> None:
  """Run all transcriptions in parallel with multiprocessing."""
  start_time: float = time.perf_counter()
  base_dir: Path = Path(__file__).resolve().parent
  project_root: Path = base_dir.parent
  input_files: list[Path] = get_input_files(base_dir)
  processes: list[Process] = []

  for input_file in input_files:
    process: Process = Process(target=run_transcription, args=(input_file, project_root))
    process.start()
    processes.append(process)

  for process in processes:
    process.join()

  elapsed_seconds: float = time.perf_counter() - start_time
  print(f"Total execution time: {elapsed_seconds:.2f}s")


if __name__ == "__main__":
  main()
