from datetime import UTC, datetime, timedelta
from subprocess import PIPE, Popen

from flask import Blueprint, Response, render_template, request
from sqlalchemy import and_, func

from cogent.base.model import Location, Node, NodeState, Room, Session

from .graph.constants import _periods
from .graph.utils import _mins

_CONTENT_SVG = "image/svg+xml"
_CONTENT_TEXT = "text/plain"

tree_bp = Blueprint("tree", __name__)


@tree_bp.route("/tree")
def tree():
    period = request.args.get("period", "day")
    debug = request.args.get("debug", "")
    mins = _mins(period)
    if debug != "y":
        cmd = "dot -Tsvg"
        mimetype = _CONTENT_SVG
    else:
        cmd = "cat"
        mimetype = _CONTENT_TEXT

    t = datetime.now(UTC) - timedelta(minutes=mins)

    with Session() as session:
        p = Popen(
            cmd, shell=True, bufsize=4096, stdin=PIPE, stdout=PIPE, close_fds=True
        )
        try:
            with p.stdin as dotfile:
                dotfile.write(b'digraph { rankdir="LR";')
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
                    dotfile.write(f'{ni}->{pa} [label="{float(rssi)}"];'.encode())
                    if ni not in seen_nodes:
                        seen_nodes.add(ni)
                        dotfile.write(f'{ni} [label="{ni}:{hi}:{rm}"];'.encode())
                dotfile.write(b"}")
            output = p.stdout.read()
        finally:
            p.stdout.close()

    return Response(output, mimetype=mimetype)


@tree_bp.route("/treePage")
def tree_page():
    period = request.args.get("period", "day")
    periods = sorted(_periods, key=lambda k: _periods[k])
    return render_template(
        "tree.html", title="Network tree diagram", period=period, periods=periods
    )
