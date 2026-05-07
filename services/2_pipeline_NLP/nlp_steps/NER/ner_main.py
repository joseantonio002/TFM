import spacy

nlp = spacy.load(
    "es_core_news_lg",
    disable=["morphologizer", "parser", "attribute_ruler", "lemmatizer", "senter"]
)

def ner_main(text: str) -> dict:
    doc = nlp(text)
    per = []
    loc = []
    org = []
    misc = []
    for ent in doc.ents:
        if ent.label_ == "PER":
            per.append(ent.text)
        elif ent.label_ == "LOC":
            loc.append(ent.text)
        elif ent.label_ == "ORG":
            org.append(ent.text)
        else:
            misc.append(ent.text)
    return {
        "entities": {
            "PER": per,
            "LOC": loc,
            "ORG": org,
            "MISC": misc
        }
    }