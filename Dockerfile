# ClientFlow AI — single-container deployment.
# The CUAD corpus and the trained model are downloaded at build time so the image
# runs offline afterwards: no outbound calls at request time, which is the whole
# point for a firm that cannot send data anywhere.
FROM python:3.12-slim

WORKDIR /app

# Only what the clause model needs; everything else is the standard library.
RUN pip install --no-cache-dir scikit-learn==1.5.2 numpy==2.1.3

COPY clientflow ./clientflow
COPY README.md docs ./docs

# Fetch corpus + train once, at build time.
RUN python -m clientflow.cli fetch-cuad && python -m clientflow.cli train

ENV CLIENTFLOW_DB=/data/clientflow.db
RUN mkdir -p /data
VOLUME ["/data"]

# Seed on first boot if the database is missing, then serve.
CMD python -m clientflow.cli --db /data/clientflow.db demo || true; \
    python -m clientflow.cli --db /data/clientflow.db serve --port ${PORT:-8770} --host 0.0.0.0

EXPOSE 8770
