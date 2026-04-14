# Image for connector test, to execute run this command in this directory: docker container run --rm --volume ./outputs/raw:/outputs/raw --volume ./outputs/common:/outputs/common test_connector:latest
FROM python:3.12-slim
RUN mkdir /outputs
RUN mkdir /outputs/raw
RUN mkdir /outputs/common
COPY ./test.py /test.py

CMD ["python", "/test.py"]