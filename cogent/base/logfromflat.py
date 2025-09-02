#
# logfromflat
#
# Convert flat file containing JSON data into mysql reading records.
#
# Author: J. Brusey, November 2019
#
# Modification history:
#

"""LogFromFlat - convert json to mysql

"""

import argparse
import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# import time
from sqlalchemy import and_, create_engine

import cogent.base.model as models
import cogent.base.model.meta as meta
from cogent.base.model import Node, NodeState, Reading, SensorType

LOGGER = logging.getLogger("ch.base")

DB_URL = os.environ.get("CH_DBURL", "mysql://chuser@localhost/ch?connect_timeout=1")
LOGFROMFLAT_DIR = os.environ.get("LOGFROMFLAT_DIR", "/data/logfromflat")

PROCESSED_FILES = os.environ.get("CH_PROCFILE", "processed-flaskapp.txt")


def duplicate_packet(session, receipt_time, node_id, localtime):
    """duplicate packets can occur because in a large network,
    the duplicate packet cache used is not sufficient. If such
    packets occur, then they will have the same node id, same
    local time and arrive within a few seconds of each other. In
    some cases, the first received copy may be corrupt and this is
    not dealt with within this code yet.
    """
    assert isinstance(receipt_time, datetime)
    earliest = receipt_time - timedelta(minutes=1)

    return (
        session.query(NodeState)
        .filter(
            and_(
                NodeState.nodeId == node_id,
                NodeState.localtime == localtime,
                NodeState.time > earliest,
            )
        )
        .first()
        is not None
    )


def add_node(session, node_id):
    """add a database entry for a node"""
    try:
        session.add(Node(id=node_id, locationId=None, nodeTypeId=(node_id // 4096)))
        session.commit()
    except Exception:
        session.rollback()
        LOGGER.exception("can't add node %d" % node_id)


class LogFromFlat(object):
    """LogFromFlat class reads a JSON file and writes sensor readings to
    the database.
    """

    def __init__(self, dbfile=None):
        """create a new LogFromFlat that reads from jsonfile and writes to dbfile"""
        self.engine = create_engine(dbfile, echo=False)
        models.initialise_sql(self.engine)

        self.log = logging.getLogger("logfromflat")
        self.create_tables()

    def create_tables(self):
        """create any missing tables using sqlalchemy"""
        try:
            with meta.Session() as session:
                models.populateData.init_data(session)
                if session.get(SensorType, 0) is None:
                    raise Exception(
                        "SensorType must be populated by alembic "
                        + "before starting LogFromFlat"
                    )
        except Exception:
            raise

    def store_state(self, msg):
        """receive and process a message object from the base station"""
        current_time = datetime.fromtimestamp(msg["server_time"], tz=timezone.utc)
        try:
            with meta.Session() as session:
                node_id = msg["sender"]
                parent_id = msg["parent"]
                seq = msg["seq"]
                rssi_val = msg["rssi"]

                node = session.get(Node, node_id)
                loc_id = None
                if node is None:
                    add_node(session, node_id)
                else:
                    loc_id = node.locationId

                if duplicate_packet(
                    session=session,
                    receipt_time=datetime.fromtimestamp(
                        msg["server_time"], tz=timezone.utc
                    ),
                    node_id=node_id,
                    localtime=msg["localtime"],
                ):
                    LOGGER.info(
                        "duplicate packet %d->%d, %d %s"
                        % (node_id, parent_id, msg["localtime"], str(msg))
                    )
                    return False

                # write a node state row
                node_state = NodeState(
                    time=datetime.fromtimestamp(msg["server_time"], tz=timezone.utc),
                    nodeId=node_id,
                    parent=parent_id,
                    localtime=msg["localtime"],
                    seq_num=seq,
                    rssi=rssi_val,
                )
                session.add(node_state)

                for i, value in list(msg.items()):
                    # skip any non-numeric type_ids
                    try:
                        type_id = int(i)
                    except ValueError:
                        continue

                    if math.isinf(value) or math.isnan(value):
                        value = None

                    st = session.get(SensorType, type_id)
                    if st is None:
                        st = SensorType(id=type_id, name="UNKNOWN", active=True)
                        session.add(st)
                        self.log.info("Adding new sensortype")
                    elif not st.active:
                        st.active = True

                    r = Reading(
                        time=current_time,
                        nodeId=node_id,
                        typeId=type_id,
                        locationId=loc_id,
                        value=value,
                    )
                    session.add(r)
                    session.flush()

                self.log.debug("reading: {}".format(node_state))
                session.commit()

        except Exception as exc:
            self.log.exception("error during storing (reading): " + str(exc))
            raise

        return True

    def process_file(self, jsonfile):
        """process a file from JSON into the database"""
        with open(jsonfile, "r") as ff:
            for ll in ff:
                msg = json.loads(ll)
                self.store_state(msg)

    def process_dir(self, datadir):
        """process directory containing json log files into the database and
        update the log of files processed"""

        processed_set = set()

        pf = datadir / PROCESSED_FILES
        if pf.exists():
            with open(str(pf), "r") as processed_files:
                processed_set = {row.rstrip() for row in processed_files}

        logfile_names = {f.name for f in datadir.glob("*.log") if not f.is_dir()}
        for name in logfile_names - processed_set:
            logfile = datadir / name
            self.log.info("Processing {}".format(logfile))
            self.process_file(logfile)

        processed_set.update(logfile_names)

        def write_pf(pf, processed_set):
            with open(str(pf), "w") as processed_files:
                for entry in processed_set:
                    processed_files.write(entry + "\n")

        try:
            write_pf(pf, processed_set)
        except PermissionError as e:
            self.log.exception(e)
            # try writing to the current directory instead

            mypf = Path.cwd() / PROCESSED_FILES
            write_pf(mypf, processed_set)
            self.log.info(
                "Couldn't write to {}, so wrote {} instead".format(str(pf), str(mypf))
            )


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dir",
        default=LOGFROMFLAT_DIR,
        help="directory containing json files containing sensor readings",
        required=True,
    )

    parser.add_argument("--database", help="database URL to log to", default=DB_URL)

    parser.add_argument(
        "-l",
        "--log-level",
        help="Set log level to LEVEL: debug,info,warning,error",
        default="debug",
        metavar="LEVEL",
    )

    parser.add_argument(
        "-f",
        "--log-file",
        help="Log file to use (omit to log only to the terminal)",
        default=None,
    )

    parser.add_argument(
        "-t",
        "--log-terminal",
        help="Echo Logging output to terminal",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    lvlmap = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    if args.log_level not in lvlmap:
        parser.error("invalid LEVEL: " + args.log_level)

    logfile = args.log_file

    logging_args = {
        "format": "%(asctime)s %(levelname)s %(message)s",
        "level": lvlmap[args.log_level],
    }
    if logfile:
        logging_args.update({"filename": logfile, "filemode": "a"})
    logging.basicConfig(**logging_args)

    # And if we want to echo the output on the terminal
    if logfile and args.log_terminal:
        console = logging.StreamHandler()
        console.setLevel(lvlmap[args.log_level])
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        console.setFormatter(formatter)
        logging.getLogger("").addHandler(console)

    logging.info("Starting LogFromFlat with log-level %s" % (args.log_level))
    lm = LogFromFlat(dbfile=args.database)
    lm.process_dir(Path(args.dir))
