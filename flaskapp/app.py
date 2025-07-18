import os

from cogent.base.model import Node, Session, init_model
from flask import Flask, render_template
from sqlalchemy import create_engine

app = Flask(__name__)

DBURL = os.environ.get("CH_DBURL", "mysql://chuser@localhost/ch?connect_timeout=1")
engine = create_engine(DBURL, echo=False, pool_recycle=60)
init_model(engine)


@app.route("/")
def index():
    return render_template("index.html", title="Home page")


@app.route("/nodes")
def nodes():
    session = Session()
    try:
        records = session.query(Node.id).all()
    finally:
        session.close()
    return render_template("nodes.html", title="Nodes", nodes=records)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
