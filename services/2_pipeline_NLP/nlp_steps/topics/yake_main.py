import yake
from keybert_main import spanish_stopwords

text = text = """
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

# With custom parameters
custom_kw_extractor = yake.KeywordExtractor(
    lan="es",              # language
    n=1,                   # ngram size
    dedupLim=0.9,          # deduplication threshold
    dedupFunc='seqm',      # deduplication function
    windowsSize=1,         # context window
    top=10,                # number of keywords to extract
    stopwords=spanish_stopwords,
    features=None          # custom features
)

keywords = custom_kw_extractor.extract_keywords(text)

for kw, score in keywords:
    print(f"{kw} ({score})")