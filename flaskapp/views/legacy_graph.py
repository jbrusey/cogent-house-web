from __future__ import annotations

import io
from datetime import datetime, timedelta

import matplotlib
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from flask import Blueprint, Response, abort, render_template, request
from matplotlib.path import Path
from sqlalchemy import and_, func
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
import sqlalchemy

from cogent.base.model import (
    House,
    Location,
    Node,
    NodeState,
    Reading,
    Room,
    Sensor,
    SensorType,
    Session,
)
from cogent.sip.sipsim import PartSplineReconstruct, SipPhenom

from .graph import _to_gviz_json

matplotlib.use("Agg")

legacy_graph_bp = Blueprint("legacy_graph", __name__)

_CONTENT_TEXT = "text/plain"
_CONTENT_PNG = "image/png"
_SAVEFIG_ARGS = {"format": "png"}
_CONTENT_PLOT = _CONTENT_PNG

thresholds: dict[int, float] = {0: 0.5, 2: 2.0, 8: 100.0, 6: 0.1, 40: 10.0}

sensor_types: dict[int, int] = {0: 0, 2: 2, 8: 8, 6: 6}

# mapping from reading type to delta type for spline reconstruction
# (subset only)
type_delta: dict[int, int] = {0: 1, 2: 3, 8: 20, 6: 7, 40: 44}

_periods: dict[str, int] = {
    "hour": 60,
    "12-hours": 60 * 12,
    "day": 1440,
    "3-days": 1440 * 3,
    "week": 1440 * 7,
    "month": 1440 * 7 * 52 // 12,
    "3-months": 3 * 1440 * 7 * 52 // 12,
    "6-months": 6 * 1440 * 7 * 52 // 12,
    "year": 12 * 1440 * 7 * 52 // 12,
    "2-years": 24 * 1440 * 7 * 52 // 12,
}


def _mins(period: str, default: int = 60) -> int:
    return _periods.get(period, default)


def _int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _get_y_label(reading_type: int, session: sqlalchemy.orm.Session) -> str:
    try:
        name, units = (
            session.query(SensorType.name, SensorType.units)
            .filter(SensorType.id == int(reading_type))
            .one()
        )
        return f"{name} ({units})"
    except NoResultFound:
        return "unknown"


def _calibrate(
    session: sqlalchemy.orm.Session, values: list[float], node: int, typ: int
) -> list[float]:
    try:
        mult, offs = (
            session.query(Sensor.calibrationSlope, Sensor.calibrationOffset)
            .filter(and_(Sensor.sensorTypeId == typ, Sensor.nodeId == node))
            .one()
        )
        return [x * mult + offs for x in values]
    except NoResultFound:
        return values


def _total_seconds(td: timedelta) -> float:
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


def _predict(sip_tuple, end_time):
    oldt, value, delta, seq = sip_tuple
    deltat = end_time - oldt
    if deltat > timedelta(hours=7):
        deltat = timedelta(hours=7)
        end_time = oldt + deltat
    return (end_time, _total_seconds(end_time - oldt) * delta + value, 0.0, seq)


def _get_value_and_delta(node_id, reading_type, delta_type, sd, ed):
    session = Session()
    try:
        try:
            (sd1,) = (
                session.query(func.max(Reading.time))
                .filter(
                    and_(
                        Reading.nodeId == node_id,
                        Reading.typeId == reading_type,
                        Reading.time < sd,
                    )
                )
                .one()
            )
            if sd1 is not None:
                sd = sd1
        except NoResultFound:
            pass
        try:
            (ed1,) = (
                session.query(func.min(Reading.time))
                .filter(
                    and_(
                        Reading.nodeId == node_id,
                        Reading.typeId == reading_type,
                        Reading.time > ed,
                    )
                )
                .one()
            )
            if ed1 is not None:
                ed = ed1
        except NoResultFound:
            pass
        s2 = aliased(Reading)
        return (
            session.query(Reading.time, Reading.value, s2.value, NodeState.seq_num)
            .join(s2, and_(Reading.time == s2.time, Reading.nodeId == s2.nodeId))
            .join(
                NodeState,
                and_(
                    Reading.time == NodeState.time, Reading.nodeId == NodeState.nodeId
                ),
            )
            .filter(
                and_(
                    Reading.typeId == reading_type,
                    s2.typeId == delta_type,
                    Reading.nodeId == node_id,
                    Reading.time >= sd,
                    Reading.time <= ed,
                )
            )
            .order_by(Reading.time)
        )
    finally:
        session.close()


def _adjust_deltas(x):
    return [(a, b, c * 300.0, d) for (a, b, c, d) in x]


def _no_data_plot():
    fig = plt.figure()
    fig.set_size_inches(7, 4)
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
    image = io.BytesIO()
    fig.savefig(image, **_SAVEFIG_ARGS)
    return [_CONTENT_PLOT, image.getvalue()]


def _plot(typ, t, v, startts, endts, debug, fmt, type_label=None):
    if not debug:
        fig = plt.figure()
        fig.set_size_inches(7, 4)
        ax = fig.add_subplot(111)
        ax.set_autoscalex_on(False)
        ax.set_xlim(
            (matplotlib.dates.date2num(startts), matplotlib.dates.date2num(endts))
        )
        if len(t) == 0:
            return _no_data_plot()
        ax.plot_date(t, v, fmt)
        fig.autofmt_xdate()
        ax.set_xlabel("Date")
        if type_label is None:
            type_label = str(typ)
        ax.set_ylabel(type_label)
        image = io.BytesIO()
        fig.savefig(image, **_SAVEFIG_ARGS)
        return [_CONTENT_PLOT, image.getvalue()]
    else:
        return [_CONTENT_TEXT, str(t) + str(v)]


def _plot_splines(
    node_id, reading_type, delta_type, start_time, end_time, debug, y_label, fmt
):
    first = True
    px = []
    py = []
    for pt in PartSplineReconstruct(
        threshold=thresholds[reading_type],
        src=SipPhenom(
            src=_adjust_deltas(
                _get_value_and_delta(
                    node_id, reading_type, delta_type, start_time, end_time
                )
            )
        ),
    ):
        dt = matplotlib.dates.date2num(pt.dt)
        if first:
            coords = [(dt, pt.sp)]
            codes = [Path.MOVETO]
            y_max = y_min = pt.sp
        else:
            coords.append((dt, pt.sp))
            codes.append(Path.LINETO)
            y_min = min(y_min, pt.sp)
            y_max = max(y_max, pt.sp)
        if pt.ev:
            px.append(dt)
            py.append(pt.sp)
            last_dt, last_s, last_t = pt.dt, pt.s, pt.t
        first = False
    if first:
        return _no_data_plot()
    path = Path(coords, codes)
    fig = plt.figure()
    fig.set_size_inches(7, 4)
    ax = fig.add_subplot(111)
    ax.set_autoscalex_on(False)
    ax.set_xlim(
        (matplotlib.dates.date2num(start_time), matplotlib.dates.date2num(end_time))
    )
    patch = patches.PathPatch(path, facecolor="none", lw=2)
    ax.add_patch(patch)
    if last_dt < end_time:
        delta_t = (end_time - last_dt).seconds
        ly = last_s + last_t * delta_t / 300.0
        lx = matplotlib.dates.date2num(end_time)
        ax.plot_date([lx], [ly], "ro")
        path = Path(
            [(matplotlib.dates.date2num(last_dt), last_s), (lx, ly)],
            [Path.MOVETO, Path.LINETO],
        )
        patch = patches.PathPatch(path, linestyle="dashed", facecolor="none", lw=2)
        ax.add_patch(patch)
    ax.plot_date(px, py, fmt)
    fig.autofmt_xdate()
    ax.set_xlabel("Date")
    ax.set_ylabel(y_label)
    image = io.BytesIO()
    fig.savefig(image, **_SAVEFIG_ARGS)
    if debug:
        return [_CONTENT_TEXT, f"px={px}\npy={py}"]
    else:
        return [_CONTENT_PLOT, image.getvalue()]


@legacy_graph_bp.route("/allGraphs")
def all_graphs():
    typ = request.args.get("typ", "0")
    period = request.args.get("period", "day")
    session = Session()
    try:
        mins = _mins(period, 1440)
        period_list = sorted(_periods, key=lambda k: _periods[k])
        graphs = []
        for node_id, house, room in (
            session.query(Node.id, House.address, Room.name)
            .join(Location, Node.locationId == Location.id)
            .join(House, Location.houseId == House.id)
            .join(Room, Location.roomId == Room.id)
            .order_by(House.address, Room.name)
        ):
            first_reading = (
                session.query(Reading)
                .filter(and_(Reading.nodeId == node_id, Reading.typeId == typ))
                .first()
            )
            if first_reading is not None:
                graphs.append(
                    {
                        "node_id": node_id,
                        "house": house,
                        "room": room,
                    }
                )
        return render_template(
            "all_graphs.html",
            title="Time series graphs",
            graphs=graphs,
            typ=typ,
            period=period,
            periods=period_list,
            mins=mins,
        )
    finally:
        session.close()


@legacy_graph_bp.route("/currentValues")
def current_values():
    typ = int(request.args.get("typ", "0"))
    session = Session()
    try:
        sensor_types = session.query(SensorType).order_by(SensorType.name).all()
        sensor = next((st for st in sensor_types if st.id == typ), None)
        max_q = (
            session.query(
                func.max(Reading.time).label("maxt"),
                Reading.nodeId.label("nodeId"),
            )
            .filter(Reading.typeId == typ)
            .group_by(Reading.nodeId)
            .subquery()
        )
        r_alias = aliased(Reading)
        qry = (
            session.query(
                r_alias.nodeId,
                r_alias.value,
                r_alias.time,
                House.address,
                Room.name,
            )
            .join(
                max_q,
                and_(r_alias.nodeId == max_q.c.nodeId, r_alias.time == max_q.c.maxt),
            )
            .filter(r_alias.typeId == typ)
            .join(Node, r_alias.nodeId == Node.id)
            .join(Location, Node.locationId == Location.id)
            .join(House, Location.houseId == House.id)
            .join(Room, Location.roomId == Room.id)
            .order_by(House.address, Room.name)
        )
        readings = []
        for node_id, value, time, house, room in qry.all():
            readings.append(
                {
                    "node": node_id,
                    "value": value,
                    "time": time,
                    "house": house,
                    "room": room,
                }
            )
        title = f"Current {sensor.name}" if sensor else "Current values"
        return render_template(
            "current_values.html",
            title=title,
            readings=readings,
            sensor=sensor,
            sensor_types=sensor_types,
            typ=typ,
        )
    finally:
        session.close()


@legacy_graph_bp.route("/nodeGraph")
def node_graph():
    node = request.args.get("node")
    if node is None:
        abort(404)
    typ = request.args.get("typ", "0")
    period = request.args.get("period", "day")
    ago = _int(request.args.get("ago", "0"))
    debug = request.args.get("debug", "n") != "n"
    session = Session()
    try:
        mins = _mins(period, 1440)
        house, room = (
            session.query(House.address, Room.name)
            .join(Location, House.id == Location.houseId)
            .join(Room, Room.id == Location.roomId)
            .join(Node, Node.locationId == Location.id)
            .filter(Node.id == int(node))
            .one()
        )
        # SQLAlchemy stores timestamps as naive UTC datetimes, so use naive
        # values here to avoid mixing timezone-aware and naive values when
        # computing deltas.
        startts = datetime.utcnow() - timedelta(minutes=(ago + 1) * mins)
        endts = startts + timedelta(minutes=mins)
        type_id = int(typ)
        node_id = int(node)
        y_label = _get_y_label(type_id, session)
        if type_id not in type_delta:
            data = (
                session.query(Reading.time, Reading.value)
                .filter(
                    and_(
                        Reading.nodeId == node_id,
                        Reading.typeId == type_id,
                        Reading.time >= startts,
                        Reading.time <= endts,
                    )
                )
                .order_by(Reading.time)
                .all()
            )
            data = [(t, v, True, v) for (t, v) in data]
        else:
            sip_data = list(
                _get_value_and_delta(
                    node_id, type_id, type_delta[type_id], startts, endts
                )
            )
            if len(sip_data) > 0 and ago == 0:
                sip_data.append(_predict(sip_data[-1], endts))
            data = list(
                PartSplineReconstruct(
                    threshold=thresholds[type_id],
                    src=SipPhenom(src=_adjust_deltas(sip_data)),
                )
            )
            data = [pt for pt in data if pt.dt >= startts and pt.dt < endts]
            data = [
                (pt.dt, pt.sp, not pt.dashed, pt.sp if pt.ev else None) for pt in data
            ]
        if len(data) > 1000:
            subs = max(len(data) // 1000, 1)
            data = [x for i, x in enumerate(data) if i % subs == 0]
        if debug:
            return Response(f"data={data!r}", mimetype=_CONTENT_TEXT)
        options = {
            "vAxis": {"title": y_label},
            "hAxis": {
                "title": "Time",
                "viewWindow": {
                    "min": int(startts.timestamp() * 1000),
                    "max": int(endts.timestamp() * 1000),
                },
                "viewWindowMode": "explicit",
            },
            "curveType": "function",
            "legend": {"position": "none"},
        }
        ev_count = sum(1 for (_, _, _, ev) in data if ev is not None)
        if ev_count < 100:
            options["series"] = {
                0: {"pointSize": 0},
                1: {"pointSize": 5, "color": "blue"},
            }
        description = [
            ("Time", "datetime"),
            ("Interpolated", "number"),
            ("", "boolean", "", {"role": "certainty"}),
            ("Event", "number"),
        ]
        json_data = _to_gviz_json(description, data)
        period_list = sorted(_periods, key=lambda k: _periods[k])
        return render_template(
            "node_graph.html",
            title="Time series graph",
            heading=f"{house}: {room} ({node})",
            json_data=json_data,
            options=options,
            periods=period_list,
            period=period,
            typ=typ,
            node_id=node,
            ago=ago,
        )
    except NoResultFound:
        # in the case that one() does not find a valid house / room for that node
        abort(404)
    finally:
        session.close()


@legacy_graph_bp.route("/plot")
def graph_image():
    node = request.args.get("node", "64")
    minsago = request.args.get("minsago", "1440")
    duration = request.args.get("duration", "1440")
    debug = request.args.get("debug")
    fmt = request.args.get("fmt", "bo")
    typ = request.args.get("typ", "0")
    session = Session()
    try:
        minsago_i = _int(minsago, 60)
        duration_i = _int(duration, 60)
        debug_f = debug is not None
        # Use naive UTC timestamps for DB comparison and plotting
        startts = datetime.utcnow() - timedelta(minutes=minsago_i)
        endts = startts + timedelta(minutes=duration_i)
        type_id = int(typ)
        if type_id not in type_delta:
            qry = (
                session.query(Reading.time, Reading.value)
                .filter(
                    and_(
                        Reading.nodeId == int(node),
                        Reading.typeId == int(typ),
                        Reading.time >= startts,
                        Reading.time <= endts,
                    )
                )
                .order_by(Reading.time)
            )
            t = []
            v = []
            for qt, qv in qry:
                t.append(matplotlib.dates.date2num(qt))
                v.append(qv)
            v = _calibrate(session, v, int(node), int(typ))
            res = _plot(
                typ,
                t,
                v,
                startts,
                endts,
                debug_f,
                fmt,
                type_label=_get_y_label(typ, session),
            )
        else:
            res = _plot_splines(
                int(node),
                type_id,
                type_delta[type_id],
                startts,
                endts,
                debug_f,
                _get_y_label(type_id, session),
                fmt,
            )
        return Response(res[1], mimetype=res[0])
    finally:
        session.close()
