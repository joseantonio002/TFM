from keybert import KeyBERT

kw_model = KeyBERT("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

text = """
La zona Quién es el problema en esta zona Para según Estados Unidos es irán 
que agita la estabilidad de la región Por lo tanto estos dos objetivos meco objetivo Digamos 
están pendientes de ser realizados Pero luego están Israel El problema de Israel es 
más grave con Irán Porque ellos lo que quieren es primero llevar a Irán a la edad 
media Que es lo que están haciendo en realidad Han destruido buena parte de la industria iraní 
Han golpeado hasta las regeneras Ya no digamos las centrales nucleares Y han llevado prácticamente 
irán a la una pobreza extrema Que de aquí décadas no levantará la cabeza en el mejor de los casos 
de las situaciones Y segundo quiere acabar con el régimen islámico Esto es so objetivo Entonces 
hasta que no consiga esto esta guerra continuará Yo lo que quiere creo es que como 
el régimen de Irán Que ahora estaba con control de los militares Porque hay un 
dato muy interesante que ha ocurrido por esta guerra Que el que le digo ha sido 
eliminado del poder de la teocracia islámica No están ya no veremos a ver 
a los hombres de Sotana En el poder Algunos pasarán por ahí por para decir 
que aquí estamos Pero el poder real estaba bajo el control de los militares En 
hecho como un denegó al prestado Incluso han apartado al presidente de la República
Islámica Que es pes esquían la han apartado prácticamente en la fan desautorizado
"""

spanish_stopwords = set("""
a ante bajo cabe con contra de desde durante en entre hacia hasta mediante
para por según sin sobre tras y o u el la los las un una unos unas
lo al del que quien quienes cuyo cuya cuyos cuyas donde cuando como
es son fue fueron será serán ha han hay haber se su sus mi mis tu tus especialmente
""".split())

keywords = kw_model.extract_keywords(
    text,
    keyphrase_ngram_range=(1, 1),
    stop_words=list(spanish_stopwords),
    top_n=10,
    use_mmr=True,
    diversity=0.5
)
print(keywords)