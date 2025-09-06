# Cogent House Docker Setup

This repository includes a small example Flask application in the `cogent/` package.
The provided Docker configuration launches the app using **Python 3** and
runs a MySQL server alongside it via Docker Compose.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency
management. After installing `uv`, create a virtual environment and install the
dependencies with:

```bash
uv venv
uv pip install -r requirements.txt
uv pip install -e .
```

## Usage

1. Build and start the services:

   ```bash
   docker compose up --build
   ```

   The Flask application will be available on [http://localhost:8000](http://localhost:8000).

2. The database credentials are defined in `docker-compose.yml` and the
   Flask container uses the `CH_DBURL` environment variable to connect.

3. To stop the containers:

   ```bash
   docker compose down
   ```

The MySQL data is stored in a named Docker volume `dbdata` so that data is
preserved between restarts.

## Apache reverse proxy (optional)

If you prefer to serve the Flask application through Apache, a sample site
configuration is provided in `cogent.conf`. Copy this file to
`/etc/apache2/sites-available/cogent.conf` and enable the required proxy
modules:

```bash
sudo a2enmod proxy proxy_http
sudo a2ensite cogent
sudo systemctl reload apache2
```

The configuration forwards requests to the app running locally on
`http://127.0.0.1:8000/` using `ProxyPass` and `ProxyPassReverse`.
