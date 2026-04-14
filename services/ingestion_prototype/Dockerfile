# Image for connector test
FROM python:3.12-slim
RUN mkdir /outputs
RUN mkdir /outputs/raw
RUN mkdir /outputs/common
COPY ./test.py /test.py

CMD ["python", "/test.py"]