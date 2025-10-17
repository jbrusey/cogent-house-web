"""Pantry should have a humidity less than some maximum

Modifications
1. 10/1/21 jpb change threshold 78 to 79

"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_

from cogent.base.model import Location, Node, Reading, Room

THRESHOLD = 79


def pantry_humid(
    session, end_t=datetime.now(UTC), start_t=(datetime.now(UTC) - timedelta(hours=24))
):
    html = []

    pantry_humidity = (
        session.query(Reading.time, Reading.value)
        .join(Reading.node)
        .join(Node.location)
        .join(Location.room)
        .filter(
            and_(
                Reading.time >= start_t,
                Reading.time <= end_t,
                Reading.typeId == 2,
                Room.name == "pantry",
            )
        )
        .order_by(Reading.time.desc())
        .first()
    )

    if pantry_humidity is not None:
        (qt, qv) = pantry_humidity
        if qv > THRESHOLD:
            html.append("<p><b>Pantry humidity is {} at {}</b></p>".format(qv, qt))
    else:
        html.append("<p><b>Pantry reading not found</b></p>")

    return html
