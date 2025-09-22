from datetime import UTC, datetime, time, timedelta

from flask import Blueprint, render_template, request
from sqlalchemy import and_, distinct, func
from sqlalchemy.orm import aliased

from cogent.base.model import (
    House,
    Location,
    Node,
    NodeState,
    Reading,
    Room,
    SensorType,
    Session,
)
from cogent.sip.calc_yield import calc_yield

main_bp = Blueprint("main", __name__)


_ELECTRICITY_SENSOR_TYPE = 40
_PERIOD_DEFINITIONS = [
    ("week", "Last 7 days", 7),
    ("month", "Last 30 days", 30),
    ("year", "Last 12 months", 365),
    ("2-years", "Last 24 months", 730),
]
_PERIOD_LOOKUP = {key: days for key, _, days in _PERIOD_DEFINITIONS}


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


@main_bp.route("/electricity-usage")
def electricity_usage():
    period = request.args.get("period", "week")
    if period not in _PERIOD_LOOKUP:
        period = "week"
    total_days = _PERIOD_LOOKUP[period]

    now = datetime.now(UTC)
    end_date = now.date()
    start_date = end_date - timedelta(days=total_days - 1)
    start_dt = datetime.combine(start_date, time.min).replace(tzinfo=None)
    end_dt = datetime.combine(end_date, time.max).replace(tzinfo=None)

    with Session() as session:
        sensor_info = (
            session.query(SensorType.name, SensorType.units)
            .filter(SensorType.id == _ELECTRICITY_SENSOR_TYPE)
            .one_or_none()
        )
        reading_day = func.date(Reading.time).label("reading_day")
        rows = (
            session.query(
                reading_day,
                Reading.nodeId,
                func.min(Reading.value),
                func.max(Reading.value),
            )
            .filter(
                Reading.typeId == _ELECTRICITY_SENSOR_TYPE,
                Reading.time >= start_dt,
                Reading.time <= end_dt,
            )
            .group_by(reading_day, Reading.nodeId)
            .all()
        )

    date_list = [start_date + timedelta(days=i) for i in range(total_days)]
    usage_by_day = {date: 0.0 for date in date_list}
    for day, _node_id, min_value, max_value in rows:
        if day is None or min_value is None or max_value is None:
            continue
        if isinstance(day, str):
            try:
                day_key = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                continue
        elif isinstance(day, datetime):
            day_key = day.date()
        else:
            day_key = day
        usage = max_value - min_value
        if usage < 0:
            continue
        usage_by_day[day_key] = usage_by_day.get(day_key, 0.0) + usage

    chart_labels = [d.strftime("%Y-%m-%d") for d in date_list]
    chart_values = [round(usage_by_day.get(d, 0.0), 3) for d in date_list]
    total_usage = round(sum(chart_values), 3)
    sensor_name = sensor_info[0] if sensor_info else "Opti Smart Count"
    sensor_units = sensor_info[1] if sensor_info and sensor_info[1] else "units"
    has_data = any(value > 0 for value in chart_values)

    period_labels = {key: label for key, label, _ in _PERIOD_DEFINITIONS}

    return render_template(
        "electricity_usage.html",
        title=f"{sensor_name} usage",
        period=period,
        period_label=period_labels[period],
        period_definitions=_PERIOD_DEFINITIONS,
        chart_labels=chart_labels,
        chart_values=chart_values,
        total_usage=f"{total_usage:.2f}",
        sensor_name=sensor_name,
        sensor_units=sensor_units,
        has_data=has_data,
        start_date=start_date,
        end_date=end_date,
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
