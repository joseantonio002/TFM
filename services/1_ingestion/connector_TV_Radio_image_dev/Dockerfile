FROM ubuntu:24.04

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
  software-properties-common && \
  add-apt-repository ppa:deadsnakes/ppa -y && \
  apt-get update && \
  apt-get install -y --no-install-recommends python3.12 python3.12-venv && \
  rm -rf /var/lib/apt/lists/*


RUN python3.12 -m venv "${VIRTUAL_ENV}"

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
  pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /opt/intel/openvino_2024.6.0 && \
    tar -xf openvino_2024.6.0.tgz -C /opt/intel/openvino_2024.6.0 --strip-components=1 && \
    rm openvino_2024.6.0.tgz && \
    cd /opt/intel/openvino_2024.6.0 && \
    ./install_dependencies/install_openvino_dependencies.sh -y && \
    cd /opt/intel && \
    ln -s openvino_2024.6.0 openvino_2024

RUN bash -lc "source /opt/intel/openvino_2024/setupvars.sh && \
    cd whisper.cpp && \
    cmake -B build -DWHISPER_OPENVINO=1 && \
    cmake --build build -j --config Release"

RUN which python && python -c "import sys; print(sys.executable)"

RUN python preload_models.py

ENTRYPOINT ["python", "main.py"]
