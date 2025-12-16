"""Fridge should be less than 10 degrees"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_

from cogent.base.model import Location, Node, Reading, Room
from cogent.config import GRAPH_HOST
from cogent.report.util import predict

THRESHOLD = 10


def fridge_open(session, end_t=None, start_t=None):
    if end_t is None:
        end_t = datetime.now(UTC)
    html = []

    fridge_node_id = (
        session.query(Node.id)
        .join(Node.location)
        .join(Location.room)
        .filter(Room.name == "fridge")
        .order_by(Node.id)
        .scalar()
    )

    if fridge_node_id is None:
        html.append("<p><b>Missing fridge temperature reading </b></p>")
        return html

    fridge_temperature = (
        session.query(Reading.time, Reading.value)
        .filter(
            and_(
                Reading.nodeId == fridge_node_id,
                Reading.typeId == 0,
                Reading.time <= end_t,
            )
        )
        .order_by(Reading.time.desc())
        .first()
    )

    if fridge_temperature is not None:
        (qt, qv) = fridge_temperature
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
            html.append(
                "<p><b>Fridge temperature is {} at {}</b></p>".format(
                    extrapolated_temperature, end_t.replace(microsecond=0)
                )
            )
    else:
        graph_link = f"{GRAPH_HOST}/nodeGraph?node={fridge_node_id}&typ=0&period=day"
        html.append(
            "<p><b>Missing fridge temperature reading</b> "
            f'<a href="{graph_link}">View fridge temperature graph</a></p>'
        )
    return html
