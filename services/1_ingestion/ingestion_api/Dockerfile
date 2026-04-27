FROM python:3.12-slim

WORKDIR /app

COPY ingestion_api/requirements.txt .

RUN pip install -U pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion_api/app ./app
COPY ingestion_api/README.md ./README.md
COPY json_to_dag ./json_to_dag

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
