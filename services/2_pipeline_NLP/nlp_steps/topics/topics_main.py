import re
import unicodedata

import yake

from .keybert_main import keybert_main, spanish_stopwords

CUSTOM_KEYWORDS: list[str] = [
  "iran",
  "israel",
  "rusia",
  "moscu",
  "china",
  "beijing",
  "taiwan",
  "taipei",
  "otan",
  "teheran",
  "isfahan",
  "tabriz",
  "pyongyang",
  "gaza",
  "hamas",
  "hezbola",
  "yemen",
  "ucrania",
  "kiev",
  "misil",
  "misiles",
  "guerra",
  "bombardeo",
  "bombardeos",
  "sanciones",
  "embargo",
  "ciberataque",
  "ransomware",
  "hackeo",
  "pandemia",
  "epidemia",
  "terremoto",
  "tsunami",
  "huracan",
  "volcan",
  "apagon",
  "estados unidos",
  "corea norte",
  "corea del norte",
  "corea sur",
  "corea del sur",
  "union europea",
  "reino unido",
  "arabia saudi",
  "franja gaza",
  "alto fuego",
  "alto el fuego",
  "ley marcial",
  "golpe estado",
  "golpe de estado",
  "guerra nuclear",
  "ataque nuclear",
  "ataque aereo",
  "ataques aereos",
  "ataque terrorista",
  "conflicto armado",
  "despliegue tropas",
  "despliegue de tropas",
  "escalada militar",
  "operacion militar",
  "ofensiva terrestre",
  "ofensiva militar",
  "ataque preventivo",
  "ataque quimico",
  "ataque biologico",
  "bomba sucia",
  "misil balistico",
  "misil de crucero",
  "defensa aerea",
  "cambio climatico",
  "salud publica",
  "corte energia",
  "corte de energia",
  "cupula hierro",
  "cupula de hierro",
  "ataque con drones",
  "ataques con drones",
  "lanzamiento de misil",
  "misiles disparados",
  "declaracion guerra",
  "declaracion de guerra",
  "guerra total",
  "guerra comercial",
  "crisis diplomatica",
  "retiro embajador",
  "retiro del embajador",
  "ayuda humanitaria",
  "tratado paz",
  "tratado de paz",
  "muchas victimas",
  "ataques masivos",
  "ataques militares",
  "ataques represalia",
  "ataques de represalia",
  "ataque represalia",
  "ataque de represalia",
  "limpieza etnica",
  "articulo 5 otan",
  "articulo 5 de la otan",
  "orden evacuacion",
  "orden de evacuacion",
  "fusion nuclear",
  "fusion del nucleo",
  "enfermedad",
  "cuarentena"
]


def normalize_text(text: str) -> str:
  """Normalize text to compare topics and keyword matches."""
  normalized_text = text.lower()
  normalized_text = unicodedata.normalize("NFKD", normalized_text)
  normalized_text = "".join(ch for ch in normalized_text if not unicodedata.combining(ch))
  normalized_text = re.sub(r"\s+", " ", normalized_text).strip()
  return normalized_text


def extract_yake_topics(text: str, ngram_size: int) -> list[str]:
  """Extract topics from text with YAKE for the requested ngram size."""
  kw_extractor = yake.KeywordExtractor(
    lan="es",
    n=ngram_size,
    dedupLim=0.9,
    dedupFunc="seqm",
    windowsSize=1,
    top=5,
    stopwords=spanish_stopwords,
    features=None,
  )
  return [keyword for keyword, _score in kw_extractor.extract_keywords(text)]


def extract_custom_keyword_topics(text: str) -> list[str]:
  """Extract matching custom topics from normalized text."""
  normalized_text = normalize_text(text)
  custom_topics: list[str] = []
  for keyword in CUSTOM_KEYWORDS:
    normalized_keyword = normalize_text(keyword)
    if re.search(rf"\b{re.escape(normalized_keyword)}\b", normalized_text):
      custom_topics.append(keyword)
  return custom_topics


def add_unique_topics(topics: list[str], new_topics: list[str], seen_topics: set[str]) -> None:
  """Add non-empty topics without duplicated normalized forms."""
  for topic in new_topics:
    clean_topic = topic.strip().lower()
    normalized_topic = normalize_text(clean_topic)
    if not normalized_topic or normalized_topic in seen_topics:
      continue
    topics.append(clean_topic)
    seen_topics.add(normalized_topic)


def topics_main(text: str) -> tuple[str, list[str]]:
  """Extract topics from text using KeyBERT, YAKE and custom keywords."""
  topics: list[str] = []
  seen_topics: set[str] = set()

  _keybert_key, keybert_keywords = keybert_main(text)
  keybert_topics = [keyword for keyword, _score in keybert_keywords]
  yake_one_word_topics = extract_yake_topics(text, 1)
  yake_two_word_topics = extract_yake_topics(text, 2)
  yake_three_word_topics = extract_yake_topics(text, 3)
  custom_keyword_topics = extract_custom_keyword_topics(text)

  add_unique_topics(topics, keybert_topics, seen_topics)
  add_unique_topics(topics, yake_one_word_topics, seen_topics)
  add_unique_topics(topics, yake_two_word_topics, seen_topics)
  add_unique_topics(topics, yake_three_word_topics, seen_topics)
  add_unique_topics(topics, custom_keyword_topics, seen_topics)

  return "topics", topics
