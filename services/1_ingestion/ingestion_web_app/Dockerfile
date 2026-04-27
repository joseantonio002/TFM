FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -U pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./app.py
COPY README.md ./README.md

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8502"]
