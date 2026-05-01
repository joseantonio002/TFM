import spacy

nlp = spacy.load(
    "es_core_news_lg",
    #disable=["morphologizer", "parser", "attribute_ruler", "lemmatizer", "senter"]
)

print(nlp.get_pipe("ner").labels)

doc = nlp("Es la Junta Municipal de la Junta Claro la Junta Municipal es para algún Bueno es verdad que la Junta Municipal es muy cercana al ciudadano En la final lo que estáis en la Junta Municipal Soy gente que todos conocemos y tenemos acceso a vosotros Y que para el día a día y para la cita a los y pequeñas Y tal pues está muy bien pero es que muchas veces olvidamos Bueno sobreviva no de forma premeditada pero se olvida Que la manga al menor tiene su propia marca y es un destino turístico A nivel nacional que es conocido a nivel internacional Y que muchísima gente y yo no por menos preciar a la región de Murcia Conoce la región de Murcia porque viene la manga al menor Entonces estamos aquí con una joya turística que no debemos presentarnos")
print([(ent.text, ent.label_) for ent in doc.ents])