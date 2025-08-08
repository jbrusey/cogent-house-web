from datetime import UTC, datetime, timedelta

from flask import Blueprint, render_template
from sqlalchemy import distinct, func

from cogent.base.model import (
    House,
    Location,
    Node,
    NodeState,
    Room,
    Session,
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html", title="Home page")


@main_bp.route("/nodes")
def nodes():
    session = Session()
    try:
        records = session.query(Node.id).all()
    finally:
        session.close()
    return render_template("nodes.html", title="Nodes", nodes=records)


@main_bp.route("/missing")
def missing():
    """Report nodes missing in the last eight hours and extra nodes."""
    t = datetime.now(UTC) - timedelta(hours=8)
    session = Session()
    try:
        report_set = {
            int(x)
            for (x,) in session.query(distinct(NodeState.nodeId))
            .filter(NodeState.time > t)
            .all()
        }
        all_set = {
            int(x)
            for (x,) in session.query(Node.id)
            .join(Location, Node.locationId == Location.id)
            .join(House, Location.houseId == House.id)
            .join(Room, Location.roomId == Room.id)
            .all()
        }
        missing_set = all_set - report_set
        extra_set = report_set - all_set

        missing_nodes = []
        if missing_set:
            qry = (
                session.query(
                    func.max(NodeState.time),
                    NodeState.nodeId,
                    House.address,
                    Room.name,
                )
                .filter(NodeState.nodeId.in_(missing_set))
                .group_by(NodeState.nodeId)
                .join(Node, NodeState.nodeId == Node.id)
                .join(Location, Node.locationId == Location.id)
                .join(House, Location.houseId == House.id)
                .join(Room, Location.roomId == Room.id)
                .order_by(House.address, Room.name)
                .all()
            )
            for maxtime, node_id, house, room in qry:
                missing_nodes.append(
                    {
                        "node": node_id,
                        "house": house,
                        "room": room,
                        "last": maxtime,
                        "unregister_url": f"/unregisterNode?node={node_id}",
                    }
                )

        extra_nodes = []
        if extra_set:
            for node_id in sorted(extra_set):
                extra_nodes.append(
                    {
                        "node": node_id,
                        "register_url": f"/registerNode?node={node_id}",
                    }
                )

    finally:
        session.close()

    return render_template(
        "missing.html", title="Missing nodes", missing=missing_nodes, extra=extra_nodes
    )
