from ast import literal_eval
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func

from cogent.base.model import House, LastReport, Location, Node, Reading, Room

LOW_BAT_REPORT_NAME = "low-bat-nodes"
BATTERY_TYPE_ID = 6


def _parse_node_set(value: str) -> set[int]:
    try:
        parsed = literal_eval(value)
    except (ValueError, SyntaxError):
        return set()

    if not isinstance(parsed, set):
        return set()

    return {int(node_id) for node_id in parsed}


def nodes_in_set(session, node_set):
    html = []
    html.append('<table border="1">')
    html.append("<tr><th>Node</th><th>House</th><th>Room</th></tr>")
    for r, addr, name in (
        session.query(Node.id, House.address, Room.name)
        .filter(Node.id.in_(node_set))
        .join(Node.location)
        .join(Location.room)
        .join(Location.house)
        .order_by(House.address, Room.name)
        .all()
    ):
        html.append("<tr><td>%d</td><td>%s</td><td>%s</td></tr>" % (r, addr, name))

    html.append("</table>")
    return html


def lowBat(
    session,
    bat_thresh=2.6,
    count_thresh=3,
    end_t=None,
    start_t=None,
):
    if end_t is None:
        end_t = datetime.now(UTC)
    if start_t is None:
        start_t = end_t - timedelta(days=1)

    html = []

    last_lowbat = (
        session.query(LastReport)
        .filter(LastReport.name == LOW_BAT_REPORT_NAME)
        .first()
    )
    last_lowbat_set = (
        _parse_node_set(last_lowbat.value) if last_lowbat is not None else set()
    )

    lowbat_set = set()
    for n, c in (
        session.query(Reading.nodeId, func.count(Reading.nodeId).label("count"))
        .filter(
            and_(
                Reading.typeId == BATTERY_TYPE_ID,
                Reading.time >= start_t,
                Reading.time < end_t,
                Reading.value < bat_thresh,
            )
        )
        .group_by(Reading.nodeId)
        .all()
    ):
        if c >= count_thresh:
            lowbat_set.add(n)

    if lowbat_set != last_lowbat_set:
        gone_low = lowbat_set - last_lowbat_set
        gone_high = last_lowbat_set - lowbat_set

        if len(gone_low) > 0:
            html.append("<h3>Nodes that have started to report low battery</h3>")
            html.extend(nodes_in_set(session, gone_low))

        if len(gone_high) > 0:
            html.append("<h3>Nodes no longer reporting low battery</h3>")
            html.extend(nodes_in_set(session, gone_high))

        if last_lowbat is None:
            last_lowbat = LastReport(name=LOW_BAT_REPORT_NAME, value=repr(lowbat_set))
            session.add(last_lowbat)
        else:
            last_lowbat.value = repr(lowbat_set)
        session.commit()

    return html


def nodesInSet(session, node_set):  # noqa: N802
    return nodes_in_set(session, node_set)
