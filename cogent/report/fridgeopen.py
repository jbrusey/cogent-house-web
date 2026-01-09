"""Fridge should be less than 10 degrees"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_

from cogent.base.model import LastReport, Location, Node, Reading, Room
from cogent.config import GRAPH_HOST
from cogent.report.util import predict

THRESHOLD = 10


def fridge_open(session, end_t=None, start_t=None):
    if end_t is None:
        end_t = datetime.now(UTC)
    html = []
    overtemp_report = (
        session.query(LastReport)
        .filter(LastReport.name == "FridgeOverTemp")
        .first()
    )
    overtemp_active = (
        overtemp_report is not None and overtemp_report.value == "True"
    )

    fridge_nodes = (
        session.query(Node.id)
        .join(Node.location)
        .join(Location.room)
        .filter(Room.name == "fridge")
    )

    first_fridge_node = fridge_nodes.order_by(Node.id).first()

    if first_fridge_node is None:
        html.append("<p><b>No 'fridge' nodes found</b></p>")
        return html

    (first_fridge_node_id,) = first_fridge_node

    graph_link = (
        f"{GRAPH_HOST}/nodeGraph?node={first_fridge_node_id}&typ=0&period=day"
    )

    fridge_temperature = (
        session.query(Reading.nodeId, Reading.time, Reading.value)
        .filter(
            and_(
                Reading.nodeId == first_fridge_node_id,
                Reading.typeId == 0,
                Reading.time <= end_t,
            )
        )
        .order_by(Reading.time.desc())
        .first()
    )

    if fridge_temperature is not None:
        fridge_node_id, qt, qv = fridge_temperature
        qt = qt.replace(tzinfo=UTC)
        rate_of_change = (
            session.query(Reading.time, Reading.value)
            .filter(
                and_(
                    Reading.nodeId == fridge_node_id,
                    Reading.typeId == 1,
                    Reading.time <= end_t,
                )
            )
            .order_by(Reading.time.desc())
            .first()
        )

        delta = rate_of_change[1] if rate_of_change is not None else 0
        _, extrapolated_temperature = predict(
            (qt, qv, delta, None), end_t, restrict=timedelta.max
        )

        if extrapolated_temperature > THRESHOLD:
            if not overtemp_active:
                if overtemp_report is None:
                    overtemp_report = LastReport(
                        name="FridgeOverTemp", value="True"
                    )
                    session.add(overtemp_report)
                else:
                    overtemp_report.value = "True"
                session.commit()
                html.append(
                    (
                        '<p><b><a href="{link}">'
                        "Extrapolated fridge temperature is {:.1f} at {}"
                        "</a></b></p>"
                    ).format(
                        extrapolated_temperature,
                        end_t.replace(microsecond=0),
                        link=graph_link,
                    )
                )
        elif overtemp_active:
            html.append("<p><b>Fridge temperature has recovered</b></p>")
            overtemp_report.value = "False"
            session.commit()
    else:
        html.append(
            "<p><b>Attempt to find last fridge temperature failed</b></p>"
            f'<p><a href="{graph_link}">View fridge temperature graph</a></p>'
        )
    return html
