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


if __name__ == "__main__":
  text: str = "La zona Quién es el problema en esta zona Para según Estados Unidos es irán que agita la estabilidad de la región Por lo tanto estos dos objetivos meco objetivo Digamos están pendientes de ser realizados Pero luego están Israel El problema de Israel es más grave con Irán Porque ellos lo que quieren es primero llevar a Irán a la edad media Que es lo que están haciendo en realidad Han destruido buena parte de la industria iraní Han golpeado hasta las regeneras Ya no digamos las centrales nucleares Y han llevado prácticamente irán a la una pobreza extrema Que de aquí décadas no levantará la cabeza en el mejor de los casos de las situaciones Y segundo quiere acabar con el régimen islámico Esto es so objetivo Entonces hasta que no consiga esto esta guerra continuará Yo lo que quiere creo es que como el régimen de Irán Que ahora estaba con control de los militares Porque hay un dato muy interesante que ha ocurrido por esta guerra Que el que le digo ha sido eliminado del poder de la teocracia islámica No están ya no veremos a ver a los hombres de Sotana En el poder Algunos pasarán por ahí por para decir que aquí estamos Pero el poder real estaba bajo el control de los militares En hecho como un denegó al prestado Incluso han apartado al presidente de la República Islámica Que es pes esquían la han apartado prácticamente en la fan desautorizado"
  sentences: List[str] = split_text_into_sentences(text)
  averages: Dict[str, float] = analyze_sentences_average(sentences)

  print(sentences)
  print(averages)
