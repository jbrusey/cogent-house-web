FROM python:3.11-slim
WORKDIR /app

# Install build tools and MySQL client libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY . /app


# Default database connection
ENV CH_DBURL mysql://chuser:chpass@db/ch?connect_timeout=1

EXPOSE 5000
CMD ["python", "flaskapp/app.py"]
