import os
import json

from NER.ner_main import ner_main

INPUT_DIR_PATH: str = "./common"
OUTPUT_DIR_PATH: str = "./outputs"

def load_metadata_from_environment() -> tuple[str, str]:
  return os.environ.get("AIRFLOW_DAG_ID", ""), os.environ.get("AIRFLOW_RUN_ID", "")


# Function that performs the NLP pipeline on the given content.
# If we want to add more steps to the pipeline, we can simply add them to this function.
def nlp_pipeline(input_json: json) -> None:
  text = input_json['content']
  input_json.update(ner_main(text))
  return input_json
  

if __name__ == "__main__":
  dag_id, run_id = load_metadata_from_environment()
  for file_name in os.listdir(INPUT_DIR_PATH):
    if file_name.startswith(f"{dag_id}_{run_id}_"):
      with open(os.path.join(INPUT_DIR_PATH, file_name), "r") as f:
        input_json = json.load(f)
        output_json = nlp_pipeline(input_json)
        with open(os.path.join(OUTPUT_DIR_PATH, file_name), "w") as f_out:
          json.dump(output_json, f_out, indent=2, ensure_ascii=False)   
      