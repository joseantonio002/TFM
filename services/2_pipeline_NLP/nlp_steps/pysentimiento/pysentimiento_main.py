from typing import Dict, List
from pysentimiento import create_analyzer

analyzer = create_analyzer(task="sentiment", lang="es")

def split_text_into_sentences(text: str, min_words: int = 10, max_words: int = 15) -> List[str]:
  """Split a text into chunks containing between min_words and max_words words."""
  words: List[str] = text.split()
  sentences: List[str] = []
  index: int = 0

  if min_words <= 0 or max_words < min_words:
    raise ValueError("Invalid word range")

  while index < len(words):
    remaining_words: int = len(words) - index
    chunk_size: int = min(max_words, remaining_words)

    if remaining_words < min_words and sentences:
      sentences[-1] = f"{sentences[-1]} {' '.join(words[index:])}"
      break

    sentence: str = " ".join(words[index:index + chunk_size])
    sentences.append(sentence)
    index += chunk_size

  return sentences


def analyze_sentences_average(sentences: List[str]) -> Dict[str, float]:
  """Analyze each sentence and return the average positive, negative, and neutral scores."""
  if not sentences:
    return {"positive": 0.0, "negative": 0.0, "neutral": 0.0}

  totals: Dict[str, float] = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
  label_map: Dict[str, str] = {"POS": "positive", "NEG": "negative", "NEU": "neutral"}

  for sentence in sentences:
    result = analyzer.predict(sentence)

    for source_label, value in result.probas.items():
      normalized_label: str | None = label_map.get(str(source_label))

      if normalized_label is not None:
        totals[normalized_label] += float(value)

  sentence_count: int = len(sentences)
  return {label: score / sentence_count for label, score in totals.items()}


def pysentimiento_main(text: str) -> dict:
  sentences = split_text_into_sentences(text)
  sent = analyze_sentences_average(sentences)
  return {
    "sentiment": sent
  }
