FROM ubuntu:24.04

ARG WHISPER_CPP_REF=v1.7.5

ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV LTP_PATH=/opt/model-cache/language-tool
ENV SENTENCE_TRANSFORMERS_HOME=/opt/model-cache/sentence-transformers
ENV HF_HOME=/opt/model-cache/huggingface

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY . .

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libgomp1 \
        openjdk-21-jre-headless \
        python3.12 \
        build-essential \
        cmake \
        curl \
        git \
        python3.12-venv; \
    \
    python3.12 -m venv "${VIRTUAL_ENV}"; \
    pip install --no-cache-dir --upgrade pip setuptools wheel; \
    pip install --no-cache-dir -r requirements.txt; \
    \
    git clone --depth 1 --branch "${WHISPER_CPP_REF}" \
        https://github.com/ggml-org/whisper.cpp.git whisper.cpp; \
    \
    cd whisper.cpp; \
    sh ./models/download-ggml-model.sh base; \
    sh ./models/download-ggml-model.sh tiny; \
    sh ./models/download-ggml-model.sh small; \
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release; \
    cmake --build build --parallel "$(nproc)"; \
    cd /app; \
    \
    python preload_models.py; \
    \
    rm -rf \
        /app/whisper.cpp/.git \
        /root/.cache \
        /tmp/*; \
    apt-get purge -y --auto-remove \
        build-essential \
        cmake \
        curl \
        git \
        python3.12-venv; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["python", "main.py"]