from keybert import KeyBERT

kw_model = KeyBERT("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

text = """
El mercado inmobiliario en España muestra señales de desaceleración,
especialmente en Madrid y Barcelona, mientras los tipos de interés siguen altos.
"""

spanish_stopwords = set("""
a ante bajo cabe con contra de desde durante en entre hacia hasta mediante
para por según sin sobre tras y o u el la los las un una unos unas
lo al del que quien quienes cuyo cuya cuyos cuyas donde cuando como
es son fue fueron será serán ha han hay haber se su sus mi mis tu tus especialmente
""".split())

keywords = kw_model.extract_keywords(
    text,
    keyphrase_ngram_range=(1, 3),
    stop_words=list(spanish_stopwords),
    top_n=10,
    use_mmr=True,
    diversity=0.5
)
print(keywords)