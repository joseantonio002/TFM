FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -U pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
