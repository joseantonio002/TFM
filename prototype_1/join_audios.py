import subprocess
from pathlib import Path


def create_files_txt(directory: Path) -> None:
  """Create files.txt with sorted WAV file paths."""
  wav_files: list[Path] = sorted(directory.glob("*_out_*.wav"), key=lambda path: path.name)
  files_txt_path: Path = directory / "files.txt"

  with files_txt_path.open("w", encoding="utf-8") as files_txt:
    for wav_file in wav_files:
      resolved_path: str = str(wav_file.resolve())
      escaped_path: str = resolved_path.replace("'", "'\\''")
      files_txt.write(f"file '{escaped_path}'\n")


def join_directory_audios(directory: Path) -> None:
  """Join WAV files in one directory into a final WAV."""
  create_files_txt(directory)
  directory_name: str = directory.name

  subprocess.run(
    [
      "ffmpeg",
      "-y",
      "-f",
      "concat",
      "-safe",
      "0",
      "-i",
      "files.txt",
      "output.wav",
      f"{directory_name}_final.wav",
    ],
    cwd=directory,
  )


def main() -> None:
  """Process every pipeline_ folder sequentially."""
  base_dir: Path = Path(".")
  pipeline_dirs: list[Path] = sorted(
    [path for path in base_dir.iterdir() if path.is_dir() and path.name.startswith("pipeline_")],
    key=lambda path: path.name,
  )

  for directory in pipeline_dirs:
    join_directory_audios(directory)


if __name__ == "__main__":
  main()
