from . import create_app
from werkzeug.middleware.proxy_fix import ProxyFix

app = create_app()
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)  # trust proxy headers

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
