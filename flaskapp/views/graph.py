import json
import os
from datetime import datetime

from flask import Blueprint, abort, render_template, request

from cogent.base.model import (
    House,
    Location,
    Node,
    Reading,
    Room,
    SensorType,
    Session,
)

graph_bp = Blueprint('graph', __name__)


def _to_gviz_json(description, data):
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


@graph_bp.route('/')
@graph_bp.route('/<int:node_id>')
@graph_bp.route('/<int:node_id>/<int:type_id>')
def graph(node_id=None, type_id=None):
    if node_id is None:
        node_id = request.args.get('node_id')
    if node_id is None:
        node_id = os.environ.get('CH_GRAPH_NODE', 23)
    if type_id is None:
        type_id = request.args.get('typ')
    if type_id is None:
        type_id = os.environ.get('CH_GRAPH_TYPE', 0)
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
        'graph.html',
        title=page_title,
        heading=heading,
        json_data=json_data,
        options=options,
    )
