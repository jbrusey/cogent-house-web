# Cogent House Docker Setup

This repository includes a small example Flask application in the `cogent/` package.
The provided Docker configuration launches the app using **Python 3** and
runs a MySQL server alongside it via Docker Compose.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency
management. After installing `uv`, create a virtual environment and install the
dependencies from the lock file to reproduce a consistent development environment:

```bash
uv venv
uv pip install -r uv.lock  # or: uv sync --dev
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

   The `cogent/daily_email.py` helper script can use the same DSN. Either
   export `CH_DBURL` before running the script or pass a custom connection
   string with `--dburl`. For example, to point at the MySQL service started by
   Docker Compose:

   ```bash
   CH_DBURL="mysql://chuser:chpass@db/ch?connect_timeout=1" \
     python cogent/daily_email.py --dry-run
   # or
   python cogent/daily_email.py --dry-run \
     --dburl mysql://chuser:chpass@db/ch?connect_timeout=1
   ```

3. To stop the containers:

   ```bash
   docker compose down
   ```

The MySQL data is stored in a named Docker volume `dbdata` so that data is
preserved between restarts.

## Daily email Gmail credentials

The `cogent/daily_email.py` script authenticates with Gmail using a pickle
file that contains the account credentials. By default the script continues to
look for `/home/chuser/auth2.pickle`, but the location can now be overridden
either by setting the `COGENT_GMAIL_AUTH_PATH` environment variable or by
passing the `--auth-file` CLI flag when invoking the script. The script checks
that the resolved file exists during startup and exits with a clear message if
it cannot be found, allowing deployments to mount the credential file wherever
is most convenient.

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
