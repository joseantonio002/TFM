


if __name__ == "__main__":
  with open("outputs/raw/test_output_raw.json", "w+") as f:
    f.write("{\"content\": \"esto es una noticia en formato raw\"}")

  with open("outputs/common/test_output_common_schema.json", "w+") as f:
    f.write("{\"content\": \"esto es una noticia en el common schema\"}")