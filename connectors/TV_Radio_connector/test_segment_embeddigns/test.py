from pathlib import Path

from segment_news import segment_algorithm

SCRIPT_DIR: Path = Path(__file__).resolve().parent
OUTPUTS_DIR: Path = SCRIPT_DIR / "outputs"
INPUT_FILES: list[str] = ["news_short.txt", "news_medium.txt", "news_long.txt"]


def build_output_dir(input_path: Path) -> Path:
  """Build the output directory for one input text file."""
  output_dir: Path = OUTPUTS_DIR / input_path.stem
  output_dir.mkdir(parents=True, exist_ok=True)
  return output_dir


def process_input_file(input_name: str) -> None:
  """Run the segmentation algorithm for one sample news file."""
  input_path: Path = SCRIPT_DIR / input_name
  output_dir: Path = build_output_dir(input_path)
  text: str = input_path.read_text(encoding="utf-8")

  segment_algorithm(text=text, output_format="file", output_dir=output_dir)
  print(f"Processed {input_path.name} -> {output_dir.relative_to(SCRIPT_DIR)}")


def main() -> None:
  """Process all sample news text files into separate output folders."""
  for input_name in INPUT_FILES:
    process_input_file(input_name)


if __name__ == "__main__":
  main()
