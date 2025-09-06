from datetime import UTC, datetime, timedelta

from flask import Blueprint, Response, render_template, request
from sqlalchemy import and_, func

from cogent.base.model import Location, Node, NodeState, Room, Session

from .graph.constants import _periods
from .graph.utils import _mins

try:
    from graphviz import Digraph
except ImportError:  # pragma: no cover - handled at runtime
    Digraph = None

_CONTENT_SVG = "image/svg+xml"
_CONTENT_TEXT = "text/plain"

tree_bp = Blueprint("tree", __name__)


@tree_bp.route("/tree")
def tree():
    if Digraph is None:  # pragma: no cover
        raise RuntimeError("graphviz is required to render network tree")

    period = request.args.get("period", "day")
    debug = request.args.get("debug", "")
    mins = _mins(period)
    t = datetime.now(UTC) - timedelta(minutes=mins)

    with Session() as session:
        dot = Digraph(format="svg")
        dot.attr(rankdir="LR")
        seen_nodes = set()
        qry = (
            session.query(
                NodeState.nodeId,
                Location.houseId,
                Room.name,
                NodeState.parent,
                func.avg(NodeState.rssi),
            )
            .join(Node, NodeState.nodeId == Node.id)
            .join(Location, Node.locationId == Location.id)
            .join(Room, Location.roomId == Room.id)
            .group_by(NodeState.nodeId, NodeState.parent)
            .filter(and_(NodeState.time > t, NodeState.parent != 65535))
        )
        for ni, hi, rm, pa, rssi in qry:
            dot.edge(str(ni), str(pa), label=f"{float(rssi)}")
            if ni not in seen_nodes:
                seen_nodes.add(ni)
                dot.node(str(ni), label=f"{ni}:{hi}:{rm}")

    if debug != "y":
        output = dot.pipe(format="svg")
        mimetype = _CONTENT_SVG
    else:
        output = dot.source.encode()
        mimetype = _CONTENT_TEXT

    return Response(output, mimetype=mimetype)


@tree_bp.route("/treePage")
def tree_page():
    period = request.args.get("period", "day")
    periods = sorted(_periods, key=lambda k: _periods[k])
    return render_template(
        "tree.html", title="Network tree diagram", period=period, periods=periods
    )
