"""Server is likely to be down if no nodes have responded in last X hours

Assume X to be 4 hours
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select

from cogent.base.model import NodeState


def server_down(
    session, end_t=datetime.now(UTC), start_t=(datetime.now(UTC) - timedelta(hours=4))
):
    html = []
    stmt = (
        select(NodeState.nodeId)
        .where(and_(NodeState.time >= start_t, NodeState.time <= end_t))
        .limit(1)
    )
    node_state = session.execute(stmt).scalar_one_or_none()

    if node_state is None:
        html.append(
            "<p><b>No nodes have reported between {} and {}</b></p>".format(
                start_t, end_t
            )
        )

    return html
