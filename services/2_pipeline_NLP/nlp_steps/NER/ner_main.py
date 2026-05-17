from pathlib import Path
import unicodedata

import spacy

TOPICS_STOPWORDS_PATH: Path = Path(__file__).resolve().parent.parent / "topics" / "topics_stopwords.txt"

nlp = spacy.load(
  "es_core_news_lg",
  disable=["morphologizer", "parser", "attribute_ruler", "lemmatizer", "senter"]
)


def normalize_text(text: str) -> str:
  """Normalize text before comparing entities with stopwords."""
  normalized_text = text.lower().strip()
  normalized_text = unicodedata.normalize("NFKD", normalized_text)
  normalized_text = "".join(ch for ch in normalized_text if not unicodedata.combining(ch))
  return " ".join(normalized_text.split())


def load_topics_stopwords() -> set[str]:
  """Load normalized topic stopwords from the shared stopwords file."""
  with TOPICS_STOPWORDS_PATH.open("r", encoding="utf-8") as file:
    return {
      normalize_text(line)
      for line in file
      if normalize_text(line)
    }


def add_unique_entity(entities: list[str], entity: str, seen_entities: set[str]) -> None:
  """Add an entity once per type using its normalized form."""
  normalized_entity = normalize_text(entity)
  if not normalized_entity or normalized_entity in seen_entities:
    return
  entities.append(entity)
  seen_entities.add(normalized_entity)


def ner_main(text: str) -> dict[str, dict[str, list[str]]]:
  """Extract named entities and remove values included in the topic stopwords list."""
  doc = nlp(text)
  topics_stopwords: set[str] = load_topics_stopwords()
  per: list[str] = []
  loc: list[str] = []
  org: list[str] = []
  misc: list[str] = []
  seen_per: set[str] = set()
  seen_loc: set[str] = set()
  seen_org: set[str] = set()
  seen_misc: set[str] = set()

  for ent in doc.ents:
    normalized_entity = normalize_text(ent.text)
    if not normalized_entity or normalized_entity in topics_stopwords:
      continue
    if ent.label_ == "PER":
      add_unique_entity(per, ent.text, seen_per)
    elif ent.label_ == "LOC":
      add_unique_entity(loc, ent.text, seen_loc)
    elif ent.label_ == "ORG":
      add_unique_entity(org, ent.text, seen_org)
    else:
      add_unique_entity(misc, ent.text, seen_misc)

  return {
    "entities": {
      "PER": per,
      "LOC": loc,
      "ORG": org,
      "MISC": misc
    }
  }
