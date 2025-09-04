import logging
import os

from flask import Flask
from sqlalchemy import create_engine
from werkzeug.middleware.proxy_fix import ProxyFix

from cogent.base.model import init_model

from .views.graph import graph_bp
from .views.main import main_bp
from .views.tree import tree_bp


def create_app():
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1, x_proto=1, x_host=1)
    db_url = os.environ.get("CH_DBURL", "mysql://chuser@localhost/ch?connect_timeout=1")
    engine = create_engine(db_url, echo=False, pool_recycle=60)
    init_model(engine)
    app.register_blueprint(main_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(tree_bp)
    return app
