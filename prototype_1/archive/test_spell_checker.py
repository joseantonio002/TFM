import language_tool_python
import ast

tool = language_tool_python.LanguageTool('es-ES')


with open('./pipeline_Onda Cero (España)/5_transcription_merged.json', 'r') as f:
    data: str = f.read()
    data: dict = ast.literal_eval(data)
    for timestamp, text in data['transcription'].items():
        print("Original: ", text)
        print("Corrected: ", tool.correct(text))
        print("-" * 40)

tool.close()