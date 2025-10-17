from datetime import UTC, datetime, timedelta

from cogent.base.model import Node, NodeState
from cogent.report.serverdown import server_down

from . import base


class TestServerDownReport(base.BaseTestCase):
    def test_server_down_when_nodes_have_reported(self):
        node = Node(id=1)
        self.session.add(node)

        report_time = datetime(2024, 1, 1, 1, tzinfo=UTC)
        self.session.add(
            NodeState(
                time=report_time,
                nodeId=node.id,
                parent=0,
                localtime=0,
                seq_num=1,
            )
        )
        self.session.flush()

        start_time = report_time - timedelta(hours=1)
        end_time = report_time + timedelta(hours=1)

        result = server_down(self.session, start_t=start_time, end_t=end_time)

        assert result == []

    def test_server_down_when_no_nodes_reported(self):
        self.session.add(Node(id=2))
        self.session.flush()

        start_time = datetime(2024, 1, 1, tzinfo=UTC)
        end_time = start_time + timedelta(hours=4)

        result = server_down(self.session, start_t=start_time, end_t=end_time)

        assert len(result) == 1
        assert "No nodes have reported" in result[0]
        assert str(start_time) in result[0]
        assert str(end_time) in result[0]
