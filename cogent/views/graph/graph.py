from __future__ import annotations

from datetime import datetime, timedelta, timezone

import matplotlib
import matplotlib.dates as mdates
from flask import Blueprint, Response, abort, render_template, request
from sqlalchemy import and_, func
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound

import cogent.base.model.meta as meta
from cogent.base.model import House, Location, Node, Reading, Room, SensorType, Session
from cogent.sip.sipsim import PartSplineReconstruct, SipPhenom

from .constants import _CONTENT_TEXT, _periods, thresholds, type_delta
from .utils import (
    _adjust_deltas,
    _calibrate,
    _get_value_and_delta,
    _get_y_label,
    _int,
    _mins,
    _plot,
    _plot_splines,
    _predict,
    _select_downsample_indices,
    _to_gviz_json,
)

graph_bp = Blueprint("graph", __name__)

MAX_CHART_POINTS = 100


@graph_bp.route("/allGraphs")
def all_graphs():
    typ = int(request.args.get("typ", "0"))
    period = request.args.get("period", "day")
    with Session() as session:
        mins = _mins(period, 1440)
        period_list = sorted(_periods, key=lambda k: _periods[k])
        sensor_types = (
            session.query(SensorType)
            .filter(SensorType.active.is_(True))
            .order_by(SensorType.name)
            .all()
        )
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
                graphs.append({"node_id": node_id, "house": house, "room": room})
        return render_template(
            "all_graphs.html",
            title="Time series graphs",
            graphs=graphs,
            typ=typ,
            period=period,
            periods=period_list,
            mins=mins,
            sensor_types=sensor_types,
        )


@graph_bp.route("/currentValues")
def current_values():
    typ = int(request.args.get("typ", "0"))
    with Session(meta.engine) as session:
        sensor_types = (
            session.query(SensorType)
            .filter(SensorType.active.is_(True))
            .order_by(SensorType.name)
            .all()
        )
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


@graph_bp.route("/nodeGraph")
def node_graph():
    node = request.args.get("node")
    if node is None:
        abort(404)
    typ = int(request.args.get("typ", "0"))
    period = request.args.get("period", "day")
    ago = _int(request.args.get("ago", "0"))
    debug = request.args.get("debug", "n") != "n"
    with Session() as session:
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
            startts = datetime.now(timezone.utc) - timedelta(minutes=(ago + 1) * mins)
            startts = startts.replace(tzinfo=None)
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
                    (pt.dt, pt.sp, not pt.dashed, pt.sp if pt.ev else None)
                    for pt in data
                ]
            if len(data) > MAX_CHART_POINTS:
                priority = [i for i, (_, _, _, ev) in enumerate(data) if ev is not None]
                times = [t for (t, _, _, _) in data]
                indices = _select_downsample_indices(times, MAX_CHART_POINTS, priority)
                data = [data[i] for i in indices]
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
            if ev_count < MAX_CHART_POINTS:
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
            sensor_types = (
                session.query(SensorType)
                .filter(SensorType.active.is_(True))
                .order_by(SensorType.name)
                .all()
            )
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
                sensor_types=sensor_types,
            )
        except NoResultFound:
            abort(404)


@graph_bp.route("/plot")
def graph_image():
    node = request.args.get("node", "64")
    minsago = request.args.get("minsago", "1440")
    duration = request.args.get("duration", "1440")
    debug = request.args.get("debug")
    fmt = request.args.get("fmt", "bo")
    typ = request.args.get("typ", "0")
    with Session() as session:
        minsago_i = _int(minsago, 60)
        duration_i = _int(duration, 60)
        debug_f = debug is not None
        startts = datetime.now(timezone.utc) - timedelta(minutes=minsago_i)
        startts = startts.replace(tzinfo=None)
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
                t.append(mdates.date2num(qt))
                v.append(qv)
            v = _calibrate(session, v, int(node), int(typ))
            if len(t) > MAX_CHART_POINTS:
                indices = _select_downsample_indices(t, MAX_CHART_POINTS)
                t = [t[i] for i in indices]
                v = [v[i] for i in indices]
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
