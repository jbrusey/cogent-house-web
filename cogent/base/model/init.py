import json
import logging

import cogent.base.model.meta as meta

from .deployment import Deployment
from .house import House
from .location import Location
from .meta import Base
from .node import Node
from .nodeboot import NodeBoot
from .nodestate import NodeState
from .nodetype import NodeType
from .reading import Reading
from .room import Room
from .roomtype import RoomType
from .sensor import Sensor
from .sensortype import SensorType

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)

TABLEMAP: dict[str, type] = {}


def init_model(engine):
    """Call me before using any of the tables or classes in the model

    DO NOT REMOVE ON MERGE
    """
    meta.engine = engine


def initialise_sql(engine, dropTables=False):
    """Initialise the database

    :param engine: Engine to use for the database
    :param dropTables: Do we want to clean the database out or not
    :param session: Use a session other than the global DB session

    .. warning::
        Previously this function called the populateData function. I
        have removed this functionality Any function that calls
        initialise_sql will have to call the init_data method if
        required

    """
    log.info("Initialising Database")
    init_model(engine)

    if dropTables:
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)


def findClass(tableName):
    """Helper method that attempts to find a SQLA class given a tablename
    :var tablename: Name of table to find
    """

    tableName = tableName.lower()
    log.debug(TABLEMAP)
    mappedTable = TABLEMAP.get(tableName, None)
    if mappedTable:
        return mappedTable

    log.debug("Looking for {0}".format(tableName))
    for mapper in Base.registry.mappers:
        log.debug("--> Checking against %s", mapper)
        checkTable = mapper.local_table
        theClass = mapper.class_
        log.debug("--> Mapped Table %s", checkTable)
        checkName = checkTable.name.lower()
        TABLEMAP[checkName] = theClass
        if checkName == tableName:
            log.debug("--> Match %s", checkTable.name)
            log.debug("--> Class is %s", theClass)
            mappedTable = theClass

    log.debug("--> Final Verison {0}".format(mappedTable))
    return mappedTable


def newClsFromJSON(jsonItem):
    """Method to create class from JSON"""
    if isinstance(jsonItem, str):
        jsonItem = json.loads(jsonItem)

    log.debug("Loading class from JSON")
    log.debug("JSON ITEM IS {0}".format(jsonItem))
    theType = jsonItem["__table__"]
    log.debug("Table from JSON is {0}".format(theType))
    theClass = findClass(theType)
    log.debug("Returned Class {0}".format(theClass))
    # Iterate through to find the class
    # Create a new instance of this model
    theModel = theClass()
    log.debug("New model is {0}".format(theModel))
    # And update using the JSON stuff
    theModel.from_json(jsonItem)
    log.debug("Updated Model {0}".format(theModel))
    return theModel


def clsFromJSON(theList):
    """Generator object to convert JSON strings from a rest object
    into database objects"""
    # Convert from JSON encoded string
    if isinstance(theList, str):
        theList = json.loads(theList)
    # Make the list object iterable
    if not isinstance(theList, list):
        theList = [theList]

    typeMap = {
        "deployment": Deployment,
        "house": House,
        "reading": Reading,
        "node": Node,
        "sensor": Sensor,
        "nodestate": NodeState,
        "nodeboot": NodeBoot,
        "roomtype": RoomType,
        "sensortype": SensorType,
        "room": Room,
        "location": Location,
        "nodetype": NodeType,
    }

    for item in theList:
        if isinstance(item, str):
            item = json.loads(item)
        # Convert to the correct type of object
        theType = item["__table__"]
        theModel = typeMap[theType.lower()]()
        # print theModel

        theModel.from_json(item)
        yield theModel
