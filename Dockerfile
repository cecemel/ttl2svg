FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir rdflib graphviz

WORKDIR /app
COPY visualize_ttl.py .

ENTRYPOINT ["python3", "visualize_ttl.py"]
