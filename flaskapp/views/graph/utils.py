from __future__ import annotations

import io
import json
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import sqlalchemy
from matplotlib.path import Path
from sqlalchemy import and_, func
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound

from cogent.base.model import NodeState, Reading, Sensor, SensorType, Session
from cogent.sip.sipsim import PartSplineReconstruct, SipPhenom

from .constants import _CONTENT_PLOT, _CONTENT_TEXT, _SAVEFIG_ARGS, _periods, thresholds


def _mins(period: str, default: int = 60) -> int:
    return _periods.get(period, default)


def _int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _to_gviz_json(description, data):
    cols = []
    for desc in description:
        col = {"label": desc[0], "type": desc[1]}
        for extra in desc[2:]:
            if isinstance(extra, dict):
                col.update(extra)
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
    with Session() as session:
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
            .all()
        )


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
