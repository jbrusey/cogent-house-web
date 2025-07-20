import os

import json
from datetime import datetime

from cogent.base.model import (
    House,
    Location,
    Node,
    Reading,
    Room,
    SensorType,
    Session,
    init_model,
)
from flask import Flask, render_template, request, abort
from sqlalchemy import create_engine

app = Flask(__name__)

DBURL = os.environ.get("CH_DBURL", "mysql://chuser@localhost/ch?connect_timeout=1")
engine = create_engine(DBURL, echo=False, pool_recycle=60)
init_model(engine)


def _to_gviz_json(description, data):
    """Return Google Visualization JSON data table string."""
    cols = []
    for desc in description:
        col = {"label": desc[0], "type": desc[1]}
        cols.append(col)

    def _conv(value, typ):
        if typ == "datetime" and isinstance(value, datetime):
            return "Date(%d,%d,%d,%d,%d,%d)" % (
                value.year,
                value.month - 1,
                value.day,
                value.hour,
                value.minute,
                value.second,
            )
        return value

    rows = []
    for row in data:
        cells = []
        for val, desc in zip(row, description):
            cells.append({"v": _conv(val, desc[1])})
        rows.append({"c": cells})
    return json.dumps({"cols": cols, "rows": rows})


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


@app.route("/graph")
@app.route("/graph/<int:node_id>")
@app.route("/graph/<int:node_id>/<int:type_id>")
def graph(node_id=None, type_id=None):
    if node_id is None:
        node_id = request.args.get("node_id")
    if node_id is None:
        node_id = os.environ.get("CH_GRAPH_NODE", 23)
    if type_id is None:
        type_id = request.args.get("typ")
    if type_id is None:
        type_id = os.environ.get("CH_GRAPH_TYPE", 0)
    try:
        node_id = int(node_id)
        type_id = int(type_id)
    except (TypeError, ValueError):
        abort(404)

    session = Session()
    try:
        records = (
            session.query(Reading.time, Reading.value)
            .filter(Reading.nodeId == node_id, Reading.typeId == type_id)
            .order_by(Reading.time)
            .limit(50)
            .all()
        )
        sensor = (
            session.query(SensorType.name, SensorType.units)
            .filter(SensorType.id == type_id)
            .one_or_none()
        )
        house_room = (
            session.query(House.address, Room.name)
            .join(Location, House.id == Location.houseId)
            .join(Room, Room.id == Location.roomId)
            .join(Node, Node.locationId == Location.id)
            .filter(Node.id == node_id)
            .one_or_none()
        )
    finally:
        session.close()

    house, room = house_room if house_room else ("Unknown", "Unknown")

    data = [(r.time, r.value) for r in records]
    description = [
        ("Time", "datetime"),
        ("Value", "number"),
    ]
    json_data = _to_gviz_json(description, data)
    label = (
        f"{sensor.name} ({sensor.units})" if sensor else f"Type {type_id}"
    )
    page_title = f"Node {node_id} {label}"
    heading = f"{house}: {room} ({node_id})"
    options = {
        "title": label,
        "legend": {"position": "none"},
        "hAxis": {"title": "Time"},
        "vAxis": {"title": label},
    }
    return render_template(
        "graph.html",
        title=page_title,
        heading=heading,
        json_data=json_data,
        options=options,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
