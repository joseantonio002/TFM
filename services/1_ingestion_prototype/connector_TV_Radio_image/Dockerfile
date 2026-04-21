FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV LTP_PATH=/opt/model-cache/language-tool
ENV SENTENCE_TRANSFORMERS_HOME=/opt/model-cache/sentence-transformers
ENV HF_HOME=/opt/model-cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  cmake \
  ffmpeg \
  openjdk-21-jdk \
  && rm -rf /var/lib/apt/lists/*

RUN python -m venv "${VIRTUAL_ENV}"

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
  pip install --no-cache-dir -r requirements.txt

COPY . .

RUN cmake -S whisper.cpp -B whisper.cpp/build && \
  cmake --build whisper.cpp/build -j --config Release

RUN python preload_models.py

ENTRYPOINT ["python", "main.py"]
