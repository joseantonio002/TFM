import spacy

nlp = spacy.load(
    "es_core_news_lg",
    disable=["morphologizer", "parser", "attribute_ruler", "lemmatizer", "senter"]
)

print(nlp.get_pipe("ner").labels)

doc = nlp("Madrid es la capital de España.")
print([(ent.text, ent.label_) for ent in doc.ents])