from datetime import UTC, datetime, timedelta

from flask import Blueprint, render_template, request
from sqlalchemy import and_, distinct, func
from sqlalchemy.orm import aliased

from cogent.base.model import House, Location, Node, NodeState, Reading, Room, Session
from cogent.sip.calc_yield import calc_yield

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html", title="Home page")


@main_bp.route("/missing")
def missing():
    """Report nodes missing in the last eight hours and extra nodes."""
    t = datetime.now(UTC) - timedelta(hours=8)
    with Session() as session:
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

    return render_template(
        "missing.html", title="Missing nodes", missing=missing_nodes, extra=extra_nodes
    )


@main_bp.route("/yield24")
def yield24():
    """Display packet yield for each node over the last 24 hours."""
    sort = request.args.get("sort", "house")
    start_t = datetime.now(UTC) - timedelta(days=1)
    with Session() as session:
        seqcnt_q = (
            session.query(
                NodeState.nodeId.label("nodeId"),
                func.count(NodeState.seq_num).label("cnt"),
            )
            .filter(NodeState.time >= start_t)
            .group_by(NodeState.nodeId)
            .subquery()
        )

        selmint_q = (
            session.query(
                NodeState.nodeId.label("nodeId"),
                func.min(NodeState.time).label("mint"),
            )
            .filter(NodeState.time >= start_t)
            .group_by(NodeState.nodeId)
            .subquery()
        )

        minseq_q = (
            session.query(
                NodeState.nodeId.label("nodeId"),
                NodeState.seq_num.label("seq_num"),
            )
            .join(
                selmint_q,
                and_(
                    NodeState.time == selmint_q.c.mint,
                    NodeState.nodeId == selmint_q.c.nodeId,
                ),
            )
            .subquery()
        )

        selmaxt_q = (
            session.query(
                NodeState.nodeId.label("nodeId"),
                func.max(NodeState.time).label("maxt"),
            )
            .filter(NodeState.time >= start_t)
            .group_by(NodeState.nodeId)
            .subquery()
        )

        maxseq_q = (
            session.query(
                NodeState.nodeId.label("nodeId"),
                NodeState.seq_num.label("seq_num"),
                NodeState.time.label("time"),
            )
            .join(
                selmaxt_q,
                and_(
                    NodeState.time == selmaxt_q.c.maxt,
                    NodeState.nodeId == selmaxt_q.c.nodeId,
                ),
            )
            .subquery()
        )

        qry = (
            session.query(
                maxseq_q.c.nodeId,
                maxseq_q.c.seq_num.label("maxseq"),
                minseq_q.c.seq_num.label("minseq"),
                seqcnt_q.c.cnt,
                maxseq_q.c.time,
                House.address,
                Room.name,
            )
            .select_from(maxseq_q)
            .join(minseq_q, minseq_q.c.nodeId == maxseq_q.c.nodeId)
            .join(seqcnt_q, seqcnt_q.c.nodeId == maxseq_q.c.nodeId)
            .join(Node, Node.id == maxseq_q.c.nodeId)
            .join(Location, Node.locationId == Location.id)
            .join(House, Location.houseId == House.id)
            .join(Room, Location.roomId == Room.id)
        )

        if sort == "id":
            qry = qry.order_by(Node.id)
        elif sort == "room":
            qry = qry.order_by(Room.name)
        elif sort == "msgcnt":
            qry = qry.order_by(seqcnt_q.c.cnt)
        elif sort == "minseq":
            qry = qry.order_by(minseq_q.c.seq_num)
        elif sort == "maxseq":
            qry = qry.order_by(maxseq_q.c.seq_num)
        elif sort == "last":
            qry = qry.order_by(maxseq_q.c.time)
        else:
            qry = qry.order_by(House.address, Room.name)

        records = []
        for (
            node_id,
            maxseq,
            minseq,
            seqcnt,
            last_heard,
            house_name,
            room_name,
        ) in qry.all():
            records.append(
                {
                    "node": node_id,
                    "house": house_name,
                    "room": room_name,
                    "msgcnt": seqcnt,
                    "minseq": minseq,
                    "maxseq": maxseq,
                    "last": last_heard,
                    "yield": calc_yield(seqcnt, minseq, maxseq),
                    "node_url": f"/nodeGraph?node={node_id}&typ=6&period=day",
                }
            )

    return render_template(
        "yield24.html", title="Yield for last day", records=records, sort=sort
    )


@main_bp.route("/lowbat")
def lowbat():
    """List nodes with low battery voltage."""
    batlvl = request.args.get("bat", "2.6")
    try:
        batlvl_f = float(batlvl)
    except (TypeError, ValueError):
        batlvl_f = 2.6
    with Session() as session:
        max_q = (
            session.query(
                func.max(Reading.time).label("maxt"),
                Reading.nodeId.label("nodeId"),
            )
            .filter(Reading.typeId == 6)
            .group_by(Reading.nodeId)
            .subquery()
        )
        r_alias = aliased(Reading)
        qry = (
            session.query(
                r_alias.nodeId,
                r_alias.value,
                House.address,
                Room.name,
            )
            .join(
                max_q,
                and_(
                    r_alias.nodeId == max_q.c.nodeId,
                    r_alias.time == max_q.c.maxt,
                ),
            )
            .filter(r_alias.typeId == 6, r_alias.value <= batlvl_f)
            .join(Node, r_alias.nodeId == Node.id)
            .join(Location, Node.locationId == Location.id)
            .join(House, Location.houseId == House.id)
            .join(Room, Location.roomId == Room.id)
            .order_by(House.address, Room.name)
        )
        rows = [
            {"node": n, "value": v, "house": h, "room": r} for n, v, h, r in qry.all()
        ]

    return render_template(
        "lowbat.html", title="Low batteries", rows=rows, bat=batlvl_f
    )
