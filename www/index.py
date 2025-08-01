#
"""
mod_python web server for simple display of cogenthouse node status

author: J. Brusey, May 2011

Modification history:
1. 11/6/2020 jpb disable unregisterNode
2. 15/3/2022 jpb fixes for problems after upgrade of cogentee

"""

import io
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from distutils.version import StrictVersion as V

import gviz_api

# do this before importing pylab or pyplot
import matplotlib
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.path import Path
from sqlalchemy import and_, create_engine, distinct, func
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound

import cogent.sip.sipsim
from cogent.base.model import (
    House,
    Location,
    Node,
    NodeState,
    Reading,
    Room,
    RoomType,
    Sensor,
    SensorType,
    Session,
    init_model,
)
from cogent.sip.calc_yield import calc_yield
from cogent.sip.sipsim import PartSplineReconstruct, SipPhenom

# set the home to a writable directory

os.environ["PYTHON_EGG_CACHE"] = "/tmp"
os.environ["HOME"] = "/tmp"
# from threading import Lock
# _lock = Lock()

_USE_SVG_PLOTS = False


matplotlib.use("Agg")


_DBURL = "mysql://chuser@localhost/ch?connect_timeout=1"

_CONTENT_SVG = "image/svg+xml"
_CONTENT_PNG = "image/png"
_CONTENT_TEXT = "text/plain"
if _USE_SVG_PLOTS:
    _CONTENT_PLOT = _CONTENT_SVG
    _SAVEFIG_ARGS = {"format": "svg"}
else:
    _CONTENT_PLOT = _CONTENT_PNG
    _SAVEFIG_ARGS = {"format": "png"}

engine = create_engine(_DBURL, echo=False, pool_recycle=60)
# engine.execute("pragma foreign_keys=on")
init_model(engine)

thresholds = {
    0: 0.5,
    2: 2,
    8: 100,
    6: 0.1,
    40: 10,
}

sensor_types = {0: 0, 2: 2, 8: 8, 6: 6}

type_delta = {0: 1, 2: 3, 8: 20, 6: 7, 40: 44}

_deltaDict = {0: 1, 2: 3, 6: 7, 8: 17}

_periods = {
    "hour": 60,
    "12-hours": 60 * 12,
    "day": 1440,
    "3-days": 1440 * 3,
    "week": 1440 * 7,
    "month": 1440 * 7 * 52 / 12,
    "3-months": 3 * 1440 * 7 * 52 / 12,
    "6-months": 6 * 1440 * 7 * 52 / 12,
    "year": 12 * 1440 * 7 * 52 / 12,
    "2-years": 24 * 1440 * 7 * 52 / 12,
}

_navs = [("Home", "index.py")]

_sidebars = [
    ("Temperature", "allGraphs?typ=0", "Show temperature graphs for all nodes"),
    ("Humidity", "allGraphs?typ=2", "Show humidity graphs for all nodes"),
    ("CO<sub>2</sub>", "allGraphs?typ=8", "Show CO2 graphs for all nodes"),
    ("AQ", "allGraphs?typ=9", "Show air quality graphs for all nodes"),
    (
        "VOC",
        "allGraphs?typ=10",
        "Show volatile organic compound (VOC) graphs for all nodes",
    ),
    ("Electricity", "allGraphs?typ=40", "Show electricity usage for all nodes"),
    ("Gas Meter", "allGraphs?typ=43", "Show gas meter usage for all nodes"),
    ("Battery", "allGraphs?typ=6", "Show node battery voltage"),
    ("Duty cycle", "allGraphs?typ=13", "Show transmission delay graphs"),
    ("Network tree", "treePage", "Show a network tree diagram"),
    ("Missing and extra nodes", "missing", "Show unregistered nodes and missing nodes"),
    ("Packet yield", "yield24", "Show network performance"),
    ("Low batteries", "lowbat?bat=2.6", "Report any low batteries"),
    ("View log", "viewLog", "View a detailed log"),
    ("Export data", "exportDataForm", "Export data to CSV"),
    (
        "Flash node",
        "flashNodePage",
        "Rewrite program code to a sensor or base station node",
    ),
]

#    ("Long term yield", "dataYield",
# "Show network performance"),
#    ("Temperature Exposure", "tempExposure",
# "Show temperature exposure graphs for all nodes"),
#    ("Humidity Exposure", "humExposure",
# "Show humidity exposure graphs for all nodes"),
#    ("Bathroom v. Elec.", "bathElec", "Show bathroom versus electricity"),


def _url(path, **kwargs):
    query = [(a, kwargs[a]) for a in kwargs]
    if query is None or len(query) == 0:
        return path
    else:
        return path + "?" + urllib.parse.urlencode(query)


def _main(html):
    return '<div id="main">' + html + "</div>"


def _wrap(html):
    return '<div id="wrap">' + html + "</div>"


def _nav():
    return (
        '<div id="nav">'
        + "<ul>"
        + "".join(
            [
                '<li><a href="%s" title="jump to %s">%s</a></li>' % (b, a, a)
                for (a, b) in _navs
            ]
        )
        + "</ul>"
        + "</div>"
    )


def _sidebar():
    return (
        '<div id="sidebar">'
        + "<ul>"
        + "".join(
            [
                '<li><a href="%s" title="%s">%s</a></li>' % (b, c, a)
                for (a, b, c) in _sidebars
            ]
        )
        + "</ul>"
        + "</div>"
    )


def _href(text, url, title=None):
    """wrap text in hyperlink"""
    if title is None:
        return '<a href="{1}">{0}</a>'.format(text, url)
    else:
        return '<a href="{1}" title="{2}">{0}</a>'.format(text, url, title)


def _bold(text):
    """wrap some text in bold"""
    return "<b>" + text + "</b>"


def _para(text):
    """wrap some text in a paragraph"""
    return "<p>" + text + "</p>"


def _row(alist, typ="d"):
    """create a table row from a list
    use _row(x, typ='h') to make headings
    """
    return (
        "<tr>" + "".join(["<t{1}>{0}</t{1}>".format(x, typ) for x in alist]) + "</tr>"
    )


def _dropdown(alist, name=""):
    """create a dropdown from a list
    each list element should be a tuple (id, displayname)
    """
    return (
        '<select name="{0}">'.format(name)
        + "".join(['<option value="{0}">{1}</option>'.format(a, b) for (a, b) in alist])
        + "</select>"
    )


def _input(typ="", name="", value=""):
    """create an input field"""
    return '<input type="{typ}" name="{name}" value="{value}"/>'.format(
        typ=typ, name=name, value=value
    )


def _form(html, action="", button="ok"):
    """create a simple form"""
    return (
        '<form action="'
        + action
        + '">'
        + html
        + '<p><input type="submit" value="'
        + button
        + '"></p></form>'
    )


def _page(title="No title", html="", script=""):
    return (
        _head(title=title, script=script)
        + _wrap(_header(title) + _nav() + _main(html) + _sidebar() + _footer())
        + _foot()
    )


def _graph_page(
    description=None,
    data=None,
    options={},
    chart_div="chart_div",
    title="No title",
    html="",
):
    """_graph_page uses google chart to draw a line graph."""
    # Loading it into gviz_api.DataTable
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(data)
    json = data_table.ToJSon()
    return _page(
        title=title,
        html=html,
        script="""<script type="text/javascript" src="https://www.google.com/jsapi"></script>
    <script type="text/javascript">
      google.load("visualization", "1", {{packages:["corechart"]}});
      google.setOnLoadCallback(drawChart);
      function drawChart() {{
        var json_data = new google.visualization.DataTable({json}, 0.6);
        var chart = new google.visualization.LineChart(document.getElementById(\'{chart_div}\'));
        var options = {options!r};
        chart.draw(json_data, options);
      }}
    </script>""".format(json=json, chart_div=chart_div, options=options),
    )


def _head(title="No title", script=""):
    return (
        "<!doctype html><html><head><title>CogentHouse Maintenance Portal - {0}</title>{1}".format(
            title, script
        )
        + '<link rel="stylesheet" type="text/css" href="../style/ccarc.css" />'
        '<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />'
        '<script type="text/javascript" src="../scripts/datePicker.js"></script></head>'
        + "<body>"
    )


def _foot():
    return "</body></html>"


def _header(title):
    return '<div id="header"><h1>%s</h1></div>' % (title)


def _footer():
    return (
        '<div id="footer">CogentHouse &copy; '
        '<a href="http://cogentcomputing.org" '
        'title="Find out more about Cogent">Cogent '
        "Computing Applied Research Centre</a></div>"
    )


def _redirect(url=""):
    return (
        "<!doctype html><html><head>"
        '<meta http-equiv="refresh" content="0;url=%s">'
        "</head><body><p>Redirecting...</p></body></html>" % url
    )


def _int(s, default=0):
    try:
        return int(s)
    except ValueError:
        return default


def _float(s, default=0.0):
    try:
        return float(s)
    except ValueError:
        return default


def _mins(s, default=60):
    if s in _periods:
        return _periods[s]
    else:
        return default


def tree(req, period="day", debug=""):
    mins = _mins(period)
    try:
        session = Session()
        from subprocess import PIPE, Popen

        if debug != "y":
            req.content_type = _CONTENT_SVG
            cmd = "dot -Tsvg"
        else:
            req.content_type = _CONTENT_TEXT
            cmd = "cat"

        t = datetime.now(UTC) - timedelta(minutes=mins)

        p = Popen(
            cmd, shell=True, bufsize=4096, stdin=PIPE, stdout=PIPE, close_fds=True
        )

        with p.stdin as dotfile:
            dotfile.write('digraph { rankdir="LR";')
            seen_nodes = set()
            qry = (
                session.query(
                    NodeState.nodeId,
                    Location.houseId,
                    Room.name,
                    NodeState.parent,
                    func.avg(NodeState.rssi),
                )
                .join(Node, NodeState.nodeId == Node.id)
                .join(Location, Node.locationId == Location.id)
                .join(Room, Location.roomId == Room.id)
                .group_by(NodeState.nodeId, NodeState.parent)
                .filter(and_(NodeState.time > t, NodeState.parent != 65535))
            )
            for ni, hi, rm, pa, rssi in qry:
                dotfile.write('{0}->{1} [label="{2}"];'.format(ni, pa, float(rssi)))
                if ni not in seen_nodes:
                    seen_nodes.add(ni)
                    dotfile.write(
                        '{ni} [label="{ni}:{hi}:{rm}"];'.format(ni=ni, hi=hi, rm=rm)
                    )

            dotfile.write("}")

        return p.stdout.read()

    finally:
        session.close()
        p.stdout.close()


def treePage(period="day"):
    s = ["<p>"]
    for k in sorted(_periods, key=lambda k: _periods[k]):
        if k == period:
            s.append(" %s " % k)
        else:
            s.append(" ")
            s.append(
                _href(k, _url("treePage", period=k), title="change period to " + k)
            )
            # s.append(' <a href="%s" title="change period to %s">%s</a> '
            # % (_url("treePage",
            #         period=k),
            #         k, k))

    u = _url("tree", period=period)
    s.append(
        _para(_href('<img src="' + u + '" alt="network tree diagram" width="700"/>', u))
    )
    # s.append('<p>')
    # s.append('<a href="%s" title="click to zoom">' % u)
    # s.append('<img src="%s" alt="network tree diagram" '
    #          'width="700"/></a></p>' % u)

    return _page("Network tree diagram", "".join(s))


def index():
    s = [""]
    s.append(
        """<p>
    Welcome to the CogentHouse Maintenance Portal</p>
    <p>This portal can be used to monitor your deployed CogentHouse
    sensors and to view graphs of all recorded data.</p>
    """
    )
    return _page("Home page", "".join(s))


def allGraphs(typ="0", period="day"):
    try:
        session = Session()

        mins = _mins(period, default=1440)

        s = ["<p>"]
        for k in sorted(_periods, key=lambda k: _periods[k]):
            if k == period:
                s.append(" %s " % k)
            else:
                u = _url("allGraphs", typ=typ, period=k)
                s.append(
                    ' <a href="%s" title="change period to %s">%s</a> ' % (u, k, k)
                )
        s.append("</p>")

        is_empty = True
        for i, h, r in (
            session.query(Node.id, House.address, Room.name)
            .join(Location, Node.locationId == Location.id)
            .join(House, Location.houseId == House.id)
            .join(Room, Location.roomId == Room.id)
            .order_by(House.address, Room.name)
        ):
            is_empty = False

            fr = (
                session.query(Reading)
                .filter(and_(Reading.nodeId == i, Reading.typeId == typ))
                .first()
            )
            if fr is not None:
                u = _url("nodeGraph", node=i, typ=typ, period=period)
                u2 = _url("graph", node=i, typ=typ, minsago=mins, duration=mins)
                s.append(
                    '<p><a href="%s"><div id="grphtitle">%s</div>'
                    '<img src="%s" alt="graph for node %d" '
                    'width="700" height="400"></a></p>'
                    % (u, h + ": " + r + " (" + str(i) + ")", u2, i)
                )

        if is_empty:
            s.append("<p>No nodes have reported yet.</p>")

        return _page("Time series graphs", "".join(s))
    finally:
        session.close()


def exportDataForm(err=None):
    errors = {
        "notype": "No sensor type has been specified",
        "nostart": "No start date specified",
        "startfmt": "Start date must be of the form dd/mm/yyyy",
        "noend": "No end date specified",
        "endfmt": "End date must be of the form dd/mm/yyyy",
        "nodata": "No data found for this sensor / period",
    }
    try:
        session = Session()
        s = []
        if err is not None:
            s.append("<p>%s</p>" % errors[err])
        s.append('<form action="getData">')

        s.append('<p>Sensor Type: <select name="sensorType">')
        for st in session.query(SensorType):
            s.append('<option value="%d">%s</option>' % (st.id, st.name))
        s.append("</select></p>")

        s.append('<table border="0" width="650" cellpadding="5"><tr><td>')
        s.append(
            'Start Date: <input type="text" '
            'name="StartDate" value="" '
            "onfocus=\"displayDatePicker('StartDate');\"/>"
        )
        # s.append("<input type=button value=\"select\"
        # onclick=\"displayDatePicker('StartDate');\"></td><td>")
        s.append("</td><td>")

        s.append(
            'End Date: <input type="text" name="EndDate" '
            'value="'
            + (datetime.now(UTC)).strftime("%d/%m/%Y")
            + '"  onfocus="displayDatePicker(\'EndDate\');"/>'
        )
        s.append("</td><tr></table>")

        s.append('<p><input type="submit" value="Get Data"></p>')

        s.append("</form>")

        return _page("Export data", "".join(s))

    finally:
        session.close()


def getData(req, sensorType=None, StartDate=None, EndDate=None):
    try:
        session = Session()
        time_format = "%d/%m/%Y"

        # Param validation
        if sensorType is None:
            return _redirect(_url("exportDataForm", err="notype"))
        st = int(sensorType)
        if StartDate is None:
            return _redirect(_url("exportDataForm", err="nostart"))
        try:
            sd = datetime.fromtimestamp(
                time.mktime(time.strptime(StartDate, time_format))
            )
        except ValueError:
            return _redirect(_url("exportDataForm", err="startfmt"))
        if EndDate is None:
            return _redirect(_url("exportDataForm", err="noend"))
        try:
            ed = datetime.fromtimestamp(
                time.mktime(time.strptime(EndDate, time_format))
            )
        except ValueError:
            return _redirect(_url("exportDataForm", err="endfmt"))

        ed = ed + timedelta(days=1)

        exportData = (
            session.query(
                Reading.nodeId, Reading.time, Reading.value, House.address, Room.name
            )
            .join(Node, Reading.nodeId == Node.id)
            .join(Location, Node.locationId == Location.id)
            .join(Room, Location.roomId == Room.id)
            .join(House, Location.houseId == House.id)
            .filter(and_(Reading.typeId == st, Reading.time >= sd, Reading.time < ed))
            .order_by(Reading.nodeId, Reading.time)
            .all()
        )
        if len(exportData) == 0:
            return _redirect(_url("exportDataForm", err="nodata"))
        req.content_type = "text/csv"
        csv_file = [
            "# cogent-house export of {0} from {1} to {2}\n".format(
                _get_y_label(st, session=session), sd, ed
            ),
            "#node id, house, room, time, value\n",
        ]
        csv_file.extend(
            [
                '{0}, "{1}", "{2}", {3}, {4}\n'.format(n, ha, rn, t, v)
                for n, t, v, ha, rn in exportData
            ]
        )
        return "".join(csv_file)
    finally:
        session.close()


def _total_seconds(td):
    """calculate the total seconds when running in python 2.6"""
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10.0**6


def _predict(sip_tuple, end_time):
    """takes in a sip_tuple containing:
    (datetime, value, delta, seq)
    and predicts the value at time end_time. returns a tuple
    with the same elements.
    Restrict forward prediction to 7 hours
    """
    (oldt, value, delta, seq) = sip_tuple
    deltat = end_time - oldt
    if deltat > timedelta(hours=7):
        deltat = timedelta(hours=7)
        end_time = oldt + deltat
    return (
        end_time,
        _total_seconds(end_time - oldt) * delta + value,
        0.0,
        seq,
    )  # repeating seq indicates uncertain data


def nodeGraph(req, node=None, typ="0", period="day", ago="0", debug="n"):
    try:
        session = Session()

        mins = _mins(period, default=1440)

        (h, r) = (
            session.query(House.address, Room.name)
            .join(Location, House.id == Location.houseId)
            .join(Room, Room.id == Location.roomId)
            .join(Node, Node.locationId == Location.id)
            .filter(Node.id == int(node))
            .one()
        )

        s = ["<p>"]
        for k in sorted(_periods, key=lambda k: _periods[k]):
            if k == period:
                s.append(" %s " % k)
            else:
                u = _url("nodeGraph", node=node, typ=typ, period=k)
                s.append(
                    ' <a href="%s" title="change period to %s">%s</a> ' % (u, k, k)
                )
        s.append("</p>")

        ago_i = _int(str(ago), default=0)
        s.append("<p>")
        s.append(
            _href(
                "<<",
                _url("nodeGraph", node=node, typ=typ, period=period, ago=ago_i + 1),
            )
        )
        if ago_i > 0:
            s.append(" &mdash; ")
            s.append(
                _href(
                    ">>",
                    _url("nodeGraph", node=node, typ=typ, period=period, ago=ago_i - 1),
                )
            )

        s.append(
            '<p><div id="grphtitle">{title}</div><div id="chart_div" '
            'style="width: 700px; height: 390px;"></div></p>'.format(
                title=h + ": " + r + " (" + node + ")"
            )
        )

        debug = debug != "n"
        startts = datetime.now(UTC) - timedelta(minutes=(ago_i + 1) * mins)

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
            if len(data) > 0:
                assert len(data[0]) == 4
        else:
            thresh = thresholds[type_id]

            sip_data = list(
                _get_value_and_delta(
                    node_id, type_id, type_delta[type_id], startts, endts
                )
            )
            if len(sip_data) > 0 and ago_i == 0:
                sip_data.append(_predict(sip_data[-1], endts))

            # TODO further fix so that it gives intervals
            assert V(cogent.sip.sipsim.__version__) >= V("0.1a1")
            data = list(
                PartSplineReconstruct(
                    threshold=thresh, src=SipPhenom(src=_adjust_deltas(sip_data))
                )
            )

            # filter out anything not in the right time range.
            data = [ptup for ptup in data if ptup.dt >= startts and ptup.dt < endts]

            def sp_if_ev(ptup):
                if ptup.ev:
                    return ptup.sp
                else:
                    return None

            data = [
                (ptup.dt, ptup.sp, not ptup.dashed, sp_if_ev(ptup)) for ptup in data
            ]
            if len(data) > 0:
                assert len(data[0]) == 4

        if len(data) > 1000:
            # trim data by sub-sampling to get the size back down to 1000
            subs = len(data) / 1000
            data = [x for i, x in enumerate(data) if i % subs == 0]

        options = {
            "vAxis": {"title": y_label},
            # 'viewWindow' : {'max':startts,
            #                 'min':endts}},
            "hAxis": {"title": "Time"},
            "curveType": "function",
            "legend": {"position": "none"},
        }
        if debug:
            req.content_type = _CONTENT_TEXT
            return "data={0!r}".format(data)

        ev_count = sum([int(ev is not None) for (a, b, c, ev) in data])
        if ev_count < 100:
            options["series"] = {
                0: {"pointSize": 0},
                1: {"pointSize": 5, "color": "blue"},
            }
            # options['pointSize'] = 5

        description = [
            ("Time", "datetime"),
            ("Interpolated", "number"),
            ("", "boolean", "", {"role": "certainty"}),
            (
                "Event",
                "number",
            ),
        ]
        return _graph_page(
            description=description,
            options=options,
            data=data,
            title="Time series graph",
            html="".join(s),
        )
    finally:
        session.close()


def viewLog(req):
    with open("/var/log/ch/LogFromFlat.log") as f:
        req.content_type = _CONTENT_TEXT
        return f.read()  # TODO limit to tail


def missing():
    try:
        t = datetime.now(UTC) - timedelta(hours=8)
        session = Session()
        s = ["<p>"]

        report_set = set(
            [
                int(x)
                for (x,) in session.query(distinct(NodeState.nodeId))
                .filter(NodeState.time > t)
                .all()
            ]
        )
        all_set = set(
            [
                int(x)
                for (x,) in session.query(Node.id).join(Location, House, Room).all()
            ]
        )
        missing_set = all_set - report_set
        extra_set = report_set - all_set

        if len(missing_set) == 0:
            s.append("No nodes missing")
        else:
            s.append(
                "</table><p><p><h3>Registered nodes "
                "not reporting in last eight hours</h3><p>"
            )

            s.append('<table border="1">')
            s.append(
                "<tr><th>Node</th><th>House</th>"
                "<th>Room</th><th>Last Heard</th><th></th></tr>"
            )

            qry = (
                session.query(
                    func.max(NodeState.time), NodeState.nodeId, House.address, Room.name
                )
                .filter(NodeState.nodeId.in_(missing_set))
                .group_by(NodeState.nodeId)
                .join(Node, NodeState.nodeId == Node.id)
                .join(Location, Node.locationId == Location.id)
                .join(House, Location.houseId == House.id)
                .join(Room, Location.roomId == Room.id)
                .order_by(House.address, Room.name)
                .all()
            )
            for maxtime, nodeId, house, room in qry:
                u = _url("unregisterNode", node=nodeId)
                s.append(
                    "<tr><td>%d</td><td>%s</td>"
                    "<td>%s</td><td>%s</td><td>"
                    '<a href="%s">(unregister)</a></tr>'
                    % (nodeId, house, room, str(maxtime), u)
                )

            s.append("</table>")

        if len(extra_set) == 0:
            s.append("</p><p>No extra nodes detected.</p><p>")
        else:
            s.append("</p><h3>Extra nodes that weren't expected</h3><p>")
            for i in sorted(extra_set):
                u = _url("registerNode", node=i)
                s.append('%d <a href="%s">(register)</a><br/>' % (i, u))

        return _page("Missing nodes", "".join(s))
    finally:
        session.close()


def lastreport():
    try:
        session = Session()

        s = []

        s.append('<table border="0">')
        s.append("<tr><th>Node</th><th>Last heard from</th>")

        for nid, maxtime in (
            session.query(NodeState.nodeId, func.max(NodeState.time))
            .group_by(NodeState.nodeId)
            .all()
        ):
            s.append("<tr><td>%d</td><td>%s</td></tr>" % (nid, maxtime))

        s.append("</table>")

        return _page("Last report", "".join(s))
    finally:
        session.close()


def yield24(sort="house"):
    """web page displaying yield for last 24 hours"""
    try:
        session = Session()
        html = []

        html.append('<table border="1">')
        html.append(
            _row(
                [
                    _href("Node", _url("yield24", sort="id")),
                    _href("House", _url("yield24", sort="house")),
                    _href("Room", _url("yield24", sort="room")),
                    _href("Message count", _url("yield24", sort="msgcnt")),
                    _href("Min seq", _url("yield24", sort="minseq")),
                    _href("Max seq", _url("yield24", sort="maxseq")),
                    _href("Last heard", _url("yield24", sort="last")),
                    "Yield",
                ],
                typ="h",
            )
        )

        start_t = datetime.now(UTC) - timedelta(days=1)

        # next get the count per node
        seqcnt_q = (
            session.query(
                NodeState.nodeId.label("nodeId"),
                func.count(NodeState.seq_num).label("cnt"),
            )
            .filter(NodeState.time >= start_t)
            .group_by(NodeState.nodeId)
            .subquery(name="seqcnt")
        )

        # next get the first occurring sequence number per node
        selmint_q = (
            session.query(
                NodeState.nodeId.label("nodeId"), func.min(NodeState.time).label("mint")
            )
            .filter(NodeState.time >= start_t)
            .group_by(NodeState.nodeId)
            .subquery(name="selmint")
        )

        minseq_q = (
            session.query(
                NodeState.nodeId.label("nodeId"), NodeState.seq_num.label("seq_num")
            )
            .join(
                selmint_q,
                and_(
                    NodeState.time == selmint_q.c.mint,
                    NodeState.nodeId == selmint_q.c.nodeId,
                ),
            )
            .subquery(name="minseq")
        )

        # next get the last occurring sequence number per node
        selmaxt_q = (
            session.query(
                NodeState.nodeId.label("nodeId"), func.max(NodeState.time).label("maxt")
            )
            .filter(NodeState.time >= start_t)
            .group_by(NodeState.nodeId)
            .subquery(name="selmaxt")
        )

        maxseq_q = (
            session.query(
                NodeState.nodeId.label("nodeId"),
                NodeState.seq_num.label("seq_num"),
                NodeState.time.label("time"),
            )
            .join(
                selmaxt_q,
                and_(
                    NodeState.time == selmaxt_q.c.maxt,
                    NodeState.nodeId == selmaxt_q.c.nodeId,
                ),
            )
            .subquery(name="maxseq")
        )

        yield_q = (
            session.query(
                maxseq_q.c.nodeId,
                maxseq_q.c.seq_num,
                minseq_q.c.seq_num,
                seqcnt_q.c.cnt,
                maxseq_q.c.time,
                House.address,
                Room.name,
            )
            .select_from(maxseq_q)
            .join(minseq_q, minseq_q.c.nodeId == maxseq_q.c.nodeId)
            .join(seqcnt_q, maxseq_q.c.nodeId == seqcnt_q.c.nodeId)
            .join(Node, Node.id == maxseq_q.c.nodeId)
            .join(Location, Node.locationId == Location.id)
            .join(House, Room)
        )
        if sort == "id":
            yield_q = yield_q.order_by(Node.id)
        elif sort == "room":
            yield_q = yield_q.order_by(Room.name)
        elif sort == "msgcnt":
            yield_q = yield_q.order_by(seqcnt_q.c.cnt)
        elif sort == "minseq":
            yield_q = yield_q.order_by(minseq_q.c.seq_num)
        elif sort == "maxseq":
            yield_q = yield_q.order_by(maxseq_q.c.seq_num)
        elif sort == "last":
            yield_q = yield_q.order_by(maxseq_q.c.time)
        else:
            yield_q = yield_q.order_by(House.address, Room.name)

        for (
            node_id,
            maxseq,
            minseq,
            seqcnt,
            last_heard,
            house_name,
            room_name,
        ) in yield_q.all():
            values = [
                node_id,
                house_name,
                room_name,
                seqcnt,
                minseq,
                maxseq,
                str(last_heard),
                calc_yield(seqcnt, minseq, maxseq),
            ]
            node_u = _url("nodeGraph", node=node_id, typ=6, period="day")
            fmt = [_href("%d", node_u), "%s", "%s", "%d", "%d", "%d", "%s", "%8.2f"]
            html.append("<tr>")
            html.extend([("<td>" + f + "</td>") % v for (f, v) in zip(fmt, values)])
            html.append("</tr>")

        html.append("</table>")
        html.append(
            "<p>The yield estimate may be an "
            "overestimate if the most recent "
            "packets have been lost or if more "
            "than 256 packets have been lost.</p>"
        )
        return _page("Yield for last day", "".join(html))
    finally:
        session.close()


def dataYield():
    try:
        session = Session()
        s = []
        s.append(
            "<h4>Note: this page does not yet "
            "support SIP and the yield may be wrong.</h4>"
        )
        s.append('<table border="1">')
        s.append(
            "<tr><th>Node</th>"
            "<th>House</th>"
            "<th>Room</th>"
            "<th>Message Count</th>"
            "<th>First heard</th><th>Last heard</th>"
            "<th>Yield</th></tr>"
        )

        # TODO finish this code
        # clock_over_count = {}
        # seq_q = (session.query(NodeState.nodeId,
        #               NodeState.seq_num)
        #     .group_by(NodeState.nodeId)
        #     .order_by(NodeState.time)
        #     .all())

        # last_node = None
        # last_seq = None
        # for node_id, seq_num in seq_q:
        #     if not node_id in clock_over_count:
        #         clock_over_count[node_id] = 0

        #     if (last_seq is not None and
        #         seq_num < last_seq and
        #         last_node is not None and
        #         node_id == last_node):
        #         clock_over_count[node_id] += 1

        #     last_seq = seq_num
        #     last_node = node_id

        for nid, cnt, mintime, maxtime in (
            session.query(
                NodeState.nodeId,
                func.count(NodeState),
                func.min(NodeState.time),
                func.max(NodeState.time),
            )
            .group_by(NodeState.nodeId)
            .all()
        ):
            try:
                n = session.query(Node).filter(Node.id == nid).one()
                try:
                    house = n.location.house.address
                except Exception:  # TODO fix unspec exception
                    house = "-"
                try:
                    room = n.location.room.name
                except Exception:  # TODO fix unspec exception
                    room = "-"
            except NoResultFound:
                house = "?"
                room = "?"

            td = maxtime - mintime
            yield_secs = td.seconds + td.days * 24 * 3600  # ignore microsecs

            y = -1
            if yield_secs > 0:
                y = (cnt - 1) / (yield_secs / 300.0) * 100.0

            s.append(
                "<tr><td>%d</td>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td>%d</td>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td>%8.2f</td></tr>" % (nid, house, room, cnt, mintime, maxtime, y)
            )

        s.append("</table>")
        return _page("Yield since first heard", "".join(s))
    finally:
        session.close()


def registerNode(node=None, room=None):
    try:
        if node is None:
            raise Exception("must specify node id")
        node = int(node)
        session = Session()
        n = session.query(Node).filter(Node.id == node).one()
        if n is None:
            raise Exception("unknown node id %d" % node)

        s = []

        s.append('<form action="registerNodeSubmit">')
        s.append(
            '<p>Node id: %d<input type="hidden" name="node" '
            'value="%d"/></p>' % (node, node)
        )
        s.append('<p>House: <select name="house">')
        for h in session.query(House):
            s.append('<option value="%d">%s</option>' % (h.id, h.address))
        s.append("</select>")
        u = _url("addNewHouse", regnode=node)
        s.append(' <a href="%s">(add new house)</a></p>' % u)
        s.append('<p>Room: <select name="room">')
        for r in session.query(Room):
            if room is not None and str(r.id) == room:
                selected = ' selected="selected"'
            else:
                selected = ""
            s.append('<option value="%d"%s>%s</option>' % (r.id, selected, r.name))
        s.append("</select>")
        u = _url("addNewRoom", regnode=node)
        s.append(' <a href="%s">(add new room)</a></p>' % u)
        s.append('<p><input type="submit" value="Register"></p>')

        s.append("</form>")

        return _page("Register node", "".join(s))

    finally:
        session.close()


def unregisterNode(node=None):
    try:
        if node is None:
            raise Exception("must specify node id")
        node = int(node)
        session = Session()
        n = session.query(Node).filter(Node.id == node).one()
        if n is None:
            raise Exception("unknown node id %d" % node)
        n = session.query(Node).filter(Node.id == int(node)).one()

        raise Exception("unregister node feature removed")
        # n.locationId = None
        session.commit()
        return _redirect("missing")

    except Exception as e:
        session.rollback()
        raise e

    finally:
        session.close()


def registerNodeSubmit(node=None, house=None, room=None):
    try:
        session = Session()

        if node is None:
            raise Exception("no node specified")
        if room is None:
            raise Exception("no room specified")
        if house is None:
            raise Exception("no house specified")

        n = session.query(Node).filter(Node.id == int(node)).one()

        ll = (
            session.query(Location)
            .filter(and_(Location.houseId == int(house), Location.roomId == int(room)))
            .first()
        )

        if ll is None:
            ll = Location(houseId=int(house), roomId=int(room))
            session.add(ll)

        n.location = ll
        session.commit()
        return _redirect("missing")

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def unregisterNodeSubmit(node=None):
    try:
        session = Session()

        if node is None:
            raise Exception("no node specified")

        n = session.query(Node).filter(Node.id == int(node)).one()

        n.locationId = None
        session.commit()
        return _redirect("missing")

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# ------------------------------------------------------------
# House


def addNewHouse(regnode=None, err=None, address=None):
    assert regnode is not None
    errors = {"duphouse": "This house address already exists"}
    if address is None:
        address = ""
    try:
        session = Session()

        s = []
        if err is not None:
            s.append("<p>%s</p>" % (errors[err]))
        s.append('<form action="addNewHouseSubmit">')
        s.append('<input type="hidden" name="regnode" value="%s" />' % (regnode))

        s.append(
            '<p>Address: <input type="text" name="address" value="%s"/></p>' % address
        )

        # s.append('<p>Deployment: <select name="deployment">')
        # for d in session.query(Deployment):
        #     s.append('<option value="%d">%s</option>' % (d.id, d.name))
        # s.append('</select>')

        s.append('<p><input type="submit" value="Add"></p>')

        s.append("</form>")

        return _page("Add new house", "".join(s))
    finally:
        session.close()


def addNewHouseSubmit(regnode=None, address=None, deployment=None):
    try:
        session = Session()

        if address is None:
            raise Exception("no address specified")
        if regnode is None:
            raise Exception("no regnode specified")

        address = address.strip().lower()

        h = session.query(House).filter(House.address == address).first()
        if h is not None:
            return _redirect(
                _url("addNewHouse", regnode=regnode, address=address, err="duphouse")
            )

        h = House(address=address, deploymentId=deployment)
        session.add(h)
        session.commit()
        u = _url("registerNode", node=regnode, house=h.id)
        return _redirect(u)
    except Exception as e:
        session.rollback()
        return _page("Add new house error", "<p>%s</p>" % str(e))
    finally:
        session.close()


# ------------------------------------------------------------
# Room


def addNewRoom(regnode=None, err=None, name=None, roomType=None):
    assert regnode is not None
    errors = {
        "duproom": "This room name already exists",
        "nullroomtype": "Please select a room type",
    }
    if name is None:
        name = ""
    try:
        session = Session()

        s = []
        if err is not None:
            s.append("<p>%s</p>" % (errors[err]))
        s.append('<form action="addNewRoomSubmit">')
        s.append('<input type="hidden" name="regnode" value="%s" />' % (regnode))
        s.append('<p>Name: <input type="text" name="name" value="%s" /></p>' % (name))
        s.append('<p>Type: <select name="roomtype">')
        for d in session.query(RoomType):
            if roomType is not None and str(d.id) == roomType:
                selected = ' selected="selected"'
            else:
                selected = ""
            s.append('<option value="%d"%s>%s</option>' % (d.id, selected, d.name))
        s.append("</select>")
        u = _url("addNewRoomType", ref=_url("addNewRoom", regnode=regnode, name=name))
        s.append(' <a href="%s">(add new room type)</a></p>' % u)

        s.append('<p><input type="submit" value="Add"></p>')

        s.append("</form>")

        return _page("Add new room", "".join(s))
    finally:
        session.close()


def addNewRoomSubmit(regnode=None, name=None, roomtype=None):
    try:
        session = Session()

        if roomtype is None:
            return _redirect(
                _url("addNewRoom", regnode=regnode, name=name, err="nullroomtype")
            )

        if name is None:
            raise Exception("no name specified")
        if regnode is None:
            raise Exception("no regnode specified")

        name = name.strip().lower()

        h = session.query(Room).filter(Room.name == name).first()
        if h is not None:
            return _redirect(
                _url("addNewRoom", regnode=regnode, name=name, err="duproom")
            )

        h = Room(name=name, roomTypeId=int(roomtype))
        session.add(h)
        session.commit()
        u = _url("registerNode", node=regnode, room=h.id)
        return _redirect(u)
    except Exception as e:
        session.rollback()
        return _page("Add new room error", "<p>%s</p>" % str(e))
    finally:
        session.close()


# ------------------------------------------------------------
# RoomType


def addNewRoomType(ref=None, err=None, name=None):
    assert ref is not None
    errors = {
        "dup": "This room type already exists",
        "short": "The room type name is too short",
    }
    if name is None:
        name = ""
    try:
        session = Session()

        s = []
        if err is not None:
            s.append("<p>%s</p>" % (errors[err]))
        s.append('<form action="addNewRoomTypeSubmit">')
        s.append('<input type="hidden" name="ref" value="%s" />' % (ref))

        s.append(
            '<p>Room type: <input type="text" name="name" value="%s" /></p>' % (name)
        )

        s.append('<p><input type="submit" value="Add">')
        s.append('    <a href="%s">Cancel</a></p>' % (ref))

        s.append("</form>")

        return _page("Add new room type", "".join(s))
    finally:
        session.close()


def addNewRoomTypeSubmit(ref=None, name=None):
    try:
        session = Session()

        if name is None:
            raise Exception("no name specified")
        if ref is None:
            raise Exception("no ref specified")

        name = name.strip().lower()
        if len(name) > 20:
            name = name[:20]
        if len(name) < 3:
            return _redirect(_url("addNewRoomType", ref=ref, name=name, err="short"))

        h = session.query(RoomType).filter(RoomType.name == name).first()
        if h is not None:
            return _redirect(_url("addNewRoomType", ref=ref, name=name, err="dup"))

        h = RoomType(name=name)
        session.add(h)
        session.commit()
        return _redirect("{0}&roomType={1}".format(ref, h.id))
    except Exception as e:
        session.rollback()
        return _page("Add new room type error", "<p>%s</p>" % str(e))
    finally:
        session.close()


def nodesInHouseList(hid=None, sort="id"):
    try:
        session = Session()

        (hname,) = (session.query(House.address).filter(House.id == int(hid))).first()

        h = (
            session.query(Node.id, Room.name)
            .join(Location, Node.locationId == Location.id)
            .join(Room, Location.roomId == Room.id)
            .join(House, Location.houseId == House.id)
            .filter(House.id == int(hid))
        )

        if sort == "id":
            h = h.order_by(Node.id)
        elif sort == "name":
            h = h.order_by(Room.name)

        s = []
        s.append('<table border="1">')
        s.append(
            _row(
                [
                    _href("id", _url("nodesInHouseList", hid=hid, sort="id")),
                    _href("room", _url("nodesInHouseList", hid=hid, sort="name")),
                ],
                typ="h",
            )
        )
        for hid, rname in h:
            u = _url("nodeGraph", node=hid)
            s.append(
                _row(
                    [
                        '<a href="{url}">{id}</a>'.format(url=u, id=hid),
                        '<a href="{url}">{id}</a>'.format(url=u, id=rname),
                    ]
                )
            )
        s.append("</table>")
        return _page("Node list for {hname}".format(hname=hname), "".join(s))
    finally:
        session.close()


def houseList():
    try:
        session = Session()
        h = session.query(House.id, House.address).order_by(House.address)

        s = []
        s.append('<table border="1">')
        for hid, hname in h:
            u = _url("nodesInHouseList", hid=hid)
            s.append(_row([_href(hid, u), _href(hname, u)]))
        s.append("</table>")
        return _page("House list", "".join(s))
    finally:
        session.close()


# ------------------------------------------------------------


def lowbat(bat="2.6"):
    """give a list of nodes with batteries less than 2.6"""
    # TODO: predict current value
    # TODO: provide estimates of battery lifetime and sort.
    try:
        batlvl = _float(bat, default=2.6)
        t = datetime.now(UTC) - timedelta(days=1)
        session = Session()
        html = []
        empty = True
        html.append("<table>")
        for (node_id,) in (
            session.query(distinct(Reading.nodeId))
            .filter(
                and_(Reading.typeId == 6, Reading.value <= batlvl, Reading.time > t)
            )
            .order_by(Reading.nodeId)
        ):
            u = _url("nodeGraph", node=node_id, typ=6, period="day")

            html.append(_row([_href(node_id, u)]))
            empty = False
        html.append("</table>")

        if empty:
            html = ["<p>No low batteries found</p>"]

        return _page("Low batteries", "".join(html))
    finally:
        session.close()


def _calibrate(session, v, node, typ):
    # calibrate
    try:
        (mult, offs) = (
            session.query(Sensor.calibrationSlope, Sensor.calibrationOffset)
            .filter(and_(Sensor.sensorTypeId == typ, Sensor.nodeId == node))
            .one()
        )
        return [x * mult + offs for x in v]
    except NoResultFound:
        return v


def _get_y_label(reading_type, session=None):
    try:
        thistype = (
            session.query(SensorType.name, SensorType.units)
            .filter(SensorType.id == int(reading_type))
            .one()
        )
        return "{0[0]} ({0[1]})".format(thistype)
    except NoResultFound:
        return "unknown"


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

        image = io.StringIO()
        fig.savefig(image, **_SAVEFIG_ARGS)

        return [_CONTENT_PLOT, image.getvalue()]
    else:
        return [_CONTENT_TEXT, str(t) + str(v)]


# ------------------------------------------------------------
# revised spline algorithm
#


def _get_value_and_delta(node_id, reading_type, delta_type, sd, ed):
    """get values and deltas given a node id, type, delta type, start
    and end date.
    """
    # make sure that time period is covered by the data
    try:
        session = Session()
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


# TODO remove this when sipsim has been fixed


def _adjust_deltas(x):
    """SipSim currently assumes that the deltas are per interval and
    the default interval is 5 minutes."""
    return [(a, b, c * 300.0, d) for (a, b, c, d) in x]


def _no_data_plot():
    """return a plot with "no data" in the centre of it."""
    fig = plt.figure()
    fig.set_size_inches(7, 4)
    ax = fig.add_subplot(111)
    ax.text(
        0.5,
        0.5,
        "No data",
        transform=ax.transAxes,
        ha="center",
        fontsize=12,
        va="center",
    )
    image = io.StringIO()
    fig.savefig(image, **_SAVEFIG_ARGS)

    return [_CONTENT_PLOT, image.getvalue()]


def _plot_splines(
    node_id, reading_type, delta_type, start_time, end_time, debug, y_label, fmt
):
    """plot splines using PartSplineReconstruct generator.  Rather
    than using matplotlib splines, a series of LINETO path elements
    are constructed based on a combination of two quadratic splines
    that are fitted together.
    """

    first = True
    px = []
    py = []
    thresh = thresholds[reading_type]
    for pt in PartSplineReconstruct(
        threshold=thresh,
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
            (last_dt, last_s, last_t) = (pt.dt, pt.s, pt.t)

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
        # the last point is prior to then end time, so estimate
        # the end point
        delta_t = (end_time - last_dt).seconds
        ly = last_s + last_t * delta_t / 300.0  # TODO fix when sipsim is fixed
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

    image = io.StringIO()
    fig.savefig(image, **_SAVEFIG_ARGS)

    if debug:
        return [_CONTENT_TEXT, "px={0}\npy={1}".format(px, py)]
    else:
        return [_CONTENT_PLOT, image.getvalue()]


def graph(
    req, node="64", minsago="1440", duration="1440", debug=None, fmt="bo", typ="0"
):
    try:
        session = Session()
        # plotLines=False

        minsago_i = _int(minsago, default=60)
        duration_i = _int(duration, default=60)

        debug = debug is not None
        # week = timedelta(minutes=int(_periods["week"]))
        startts = datetime.now(UTC) - timedelta(minutes=minsago_i)
        # deltats = (datetime.utcnow() - minsago_i) - week

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
            dt = []
            v = []
            # last_value=None
            for qt, qv in qry:
                dt.append(qt)
                t.append(matplotlib.dates.date2num(qt))
                v.append(qv)
                # last_value=float(qv)

            v = _calibrate(session, v, node, typ)
            res = _plot(
                typ,
                t,
                v,
                startts,
                endts,
                debug,
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
                debug,
                _get_y_label(type_id, session),
                fmt,
            )

        req.content_type = res[0]
        return res[1]
    finally:
        session.close()


def _get_motelist():
    from subprocess import PIPE, Popen

    devs = []
    try:
        p = Popen(
            "motelist -c",
            shell=True,
            bufsize=4096,
            stdin=None,
            stdout=PIPE,
            close_fds=True,
        )

        for ll in p.stdout:
            ss = ll.split(", ")
            if len(ss) > 1:
                devs.append(ss[1])
    finally:
        p.stdout.close()
    return devs
