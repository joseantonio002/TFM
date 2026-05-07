from keybert import KeyBERT

kw_model = KeyBERT("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

spanish_stopwords = set("""
a ante bajo cabe con contra de desde durante en entre hacia hasta mediante
para por según sobre tras y o u el la los las un una unos unas
lo al del que quien quienes cuyo cuya cuyos cuyas donde cuando como
es son fue fueron será serán ha han hay haber se su sus mi mis tu tus especialmente
""".split())

extra_stopwords = set("""
yo me mí conmigo
tú te ti contigo usted ustedes
él ella ello ellos ellas
nos nosotros nosotras
vos vosotros vosotras
le les
este esta estos estas
ese esa esos esas
aquel aquella aquellos aquellas
esto eso aquello

qué cuál cuáles cuánto cuánta cuántos cuántas
porque pues ya si sí
también tampoco muy más menos mucho mucha muchos muchas
poco poca pocos pocas
tan tanto tanta tantos tantas
todo toda todos todas
algún alguna algunos algunas
ningún ninguna ningunos ningunas
otro otra otros otras
mismo misma mismos mismas
cada cualquier cualquiera

ser estar estoy estás está estamos están
soy eres somos sois
era eras éramos eran
fui fuiste fuimos fueron
sea seas seamos sean
sido siendo

tener tengo tienes tiene tenemos tienen
tenía tenían tuvo tuvieron
hacer hago hace hacemos hacen
hizo hicieron hecho
poder puedo puedes puede podemos pueden
podía podían pudo pudieron
deber debe deben debía debían
ir voy vas va vamos van
iba iban fue fueron ido

he has hemos habéis
había habían hubo
será serán sería serían

aquí allí ahí allá acá
entonces luego después antes ahora hoy ayer mañana
siempre nunca jamás mientras

aunque sino pero mas
además asimismo incluso excepto salvo
respecto acerca mediante
debido través vez veces

forma manera caso parte tipo nivel
ejemplo información datos resultado resultados
uso usos proceso procesos
tema temas aspecto aspectos
""".split())


spanish_stopwords = list(spanish_stopwords | extra_stopwords)


def keybert_main(text: str) -> dict:
    keywords = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 1),
        stop_words=spanish_stopwords,
        top_n=8,
        use_mmr=True,
        diversity=0.5
    )
    return "topics_keybert", keywords