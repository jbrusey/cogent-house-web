"""Fridge should be less than 10 degrees"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_

from cogent.base.model import Location, Node, Reading, Room

THRESHOLD = 10


def fridge_open(
    session, end_t=datetime.now(UTC), start_t=(datetime.now(UTC) - timedelta(hours=4))
):
    html = []

    fridge_temperature = (
        session.query(Reading.time, Reading.value)
        .join(Reading.node)
        .join(Node.location)
        .join(Location.room)
        .filter(
            and_(
                Reading.time >= start_t,
                Reading.time <= end_t,
                Reading.typeId == 0,
                Room.name == "fridge",
            )
        )
        .order_by(Reading.time.desc())
        .first()
    )

    if fridge_temperature is not None:
        (qt, qv) = fridge_temperature
        if qv > THRESHOLD:
            html.append("<p><b>Fridge temperature is {} at {}</b></p>".format(qv, qt))
    else:
        html.append("<p><b>Missing fridge temperature reading </b></p>")
    return html
