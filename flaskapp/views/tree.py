from datetime import UTC, datetime, timedelta
from subprocess import PIPE, Popen

from flask import Blueprint, Response, render_template, request
from sqlalchemy import and_, func

from cogent.base.model import Location, Node, NodeState, Room, Session

_CONTENT_SVG = "image/svg+xml"
_CONTENT_TEXT = "text/plain"

_periods = {
    "hour": 60,
    "12-hours": 60 * 12,
    "day": 1440,
    "3-days": 1440 * 3,
    "week": 1440 * 7,
    "month": 1440 * 7 * 52 / 12,
    "3-months": 3 * 1440 * 7 * 52 / 12,
    "6-months": 6 * 1440 * 7 * 52 / 12,
    "year": 12 * 1440 * 7 * 52 / 12,
    "2-years": 24 * 1440 * 7 * 52 / 12,
}


def _mins(period: str, default: int = 60) -> int:
    return _periods.get(period, default)


tree_bp = Blueprint("tree", __name__)


@tree_bp.route("/tree")
def tree():
    period = request.args.get("period", "day")
    debug = request.args.get("debug", "")
    mins = _mins(period)
    session = Session()

    if debug != "y":
        cmd = "dot -Tsvg"
        mimetype = _CONTENT_SVG
    else:
        cmd = "cat"
        mimetype = _CONTENT_TEXT

    t = datetime.now(UTC) - timedelta(minutes=mins)

    p = Popen(cmd, shell=True, bufsize=4096, stdin=PIPE, stdout=PIPE, close_fds=True)
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
                dotfile.write(f"{ni}->{pa} [label=\"{float(rssi)}\"];".encode())
                if ni not in seen_nodes:
                    seen_nodes.add(ni)
                    dotfile.write(f"{ni} [label=\"{ni}:{hi}:{rm}\"];".encode())
            dotfile.write(b"}")
        output = p.stdout.read()
    finally:
        session.close()
        p.stdout.close()

    return Response(output, mimetype=mimetype)


@tree_bp.route("/treePage")
def tree_page():
    period = request.args.get("period", "day")
    periods = sorted(_periods, key=lambda k: _periods[k])
    return render_template(
        "tree.html", title="Network tree diagram", period=period, periods=periods
    )
