FROM python:3.11-slim
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

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY . /app
# Install the local cogent package in editable mode so the Flask app
# can import it.
RUN pip install --no-cache-dir -e .


# Default database connection
ENV CH_DBURL mysql://chuser:chpass@db/ch?connect_timeout=1
ENV LOGFROMFLAT_DIR=/data/silicon

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "flaskapp.app:app"]
