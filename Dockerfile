FROM ghcr.io/astral-sh/uv:python3.11-slim
WORKDIR /app

# Install build tools and MySQL client libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        pkg-config \
        graphviz \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app
# Install the local cogent package in editable mode so the Flask app
# can import it.
RUN uv pip install --system -e .


# Default database connection
ENV CH_DBURL mysql://chuser:chpass@db/ch?connect_timeout=1
ENV LOGFROMFLAT_DIR=/data/silicon

EXPOSE 8000
CMD ["uv", "run", "gunicorn", \
     "-b", "0.0.0.0:8000", \
     "--workers=3", \
     "--threads=2", \
     "--timeout=60", \
     "--forwarded-allow-ips=*", \
     "--access-logfile=-", \
     "--error-logfile=-", \
     "--worker-tmp-dir", "/dev/shm", \
     "cogent.app:app"]
