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

   The daily email identifies the host that generated the report in both the
   `From:` header and subject line. Override these defaults with either command
   line flags or environment variables when running inside Docker:

   * `--from-address` / `COGENT_EMAIL_FROM` &ndash; sender email address to place
     in the `From:` header.
   * `--hostname` / `COGENT_EMAIL_HOSTNAME` &ndash; hostname label used in the
     subject and angle-bracket identifier.

   When neither option is provided the script falls back to
   `platform.node()` to describe the host, mirroring the previous behaviour.

3. To stop the containers:

   ```bash
   docker compose down
   ```

The MySQL data is stored in a named Docker volume `dbdata` so that data is
preserved between restarts.

## Automated container publishing and Watchtower updates

Pushes to the `main` branch automatically build the web service image in this
repository and publish it to GitHub Container Registry via a GitHub Actions
workflow. Images are tagged for branches, Git tags, and the committing SHA, so
the `ghcr.io/jbrusey/cogent-house-web:main` tag will stay up to date with the latest
mainline changes.

Because this project normally runs under Docker Compose (with a MySQL sidecar),
use the published image from GHCR by setting the `WEB_IMAGE` environment
variable for the Compose project:

```bash
WEB_IMAGE=ghcr.io/jbrusey/cogent-house-web:main docker compose pull web
WEB_IMAGE=ghcr.io/jbrusey/cogent-house-web:main docker compose up -d
```

This keeps the `db` container on the official `mysql:5.7` image while the `web`
service tracks the GHCR build.

You can use [Watchtower](https://containrrr.dev/watchtower/) to monitor the
Compose-managed web container and restart it when a new tag is pushed. After
authenticating to GHCR with `docker login ghcr.io`, run Watchtower and scope it
to the Compose-managed container name (for a project directory named
`cogent-house-web`, that container is `cogent-house-web-web-1`):

```bash
docker run -d --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower  \
  --interval 30 --cleanup \
  cogent-house-web-web-1
```

Watchtower will poll GHCR for updates to the web image and recreate the
container when a new build is published. To watch a differently named Compose
project, swap in that project's web container name (you can check it with
`docker compose ps`).

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
