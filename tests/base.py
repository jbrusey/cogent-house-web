"""Metaclass to bring everything together in a simulation of a Pyramid environment

This really just makes sure all database code is in the same place
meaning the DB is consistently initiated in all test cases.
"""

import logging
import unittest

import sqlalchemy
from sqlalchemy.orm import sessionmaker

import cogent.base.model as models
import cogent.base.model.meta as meta
from cogent.base.model import init_data

# from pyramid.config import Configurator
# from paste.deploy.loadwsgi import appconfig
# from pyramid import testing


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def initDatabase():
    """Method to initialise the database"""

    log.debug("------- INITIALISE TESTING DATABASE ---------")
    # settings = appconfig('config:' + SETTINGS_PATH)
    # engine = engine_from_config(settings,prefix="sqlalchemy.")
    engine = sqlalchemy.create_engine("sqlite:///test.db")

    log.debug("Database Engine Started: {0}".format(engine))

    meta.Session.configure(bind=engine)
    meta.Base.metadata.create_all(engine)


# Track if we have already initialised the test database to avoid recreating it
TEST_DB_INITIALISED = False

if not TEST_DB_INITIALISED:
    log.info("No Database Initiated")
    initDatabase()
    init_data()
    TEST_DB_INITIALISED = True


class BaseTestCase(unittest.TestCase):
    """Base class for testing"""

    @classmethod
    def setUpClass(cls):
        """Class method, called each time this is initialised"""
        # cls.config = testing.setUp()

        # Load settings from Configuration file
        log.debug("Initialising Test Class Database for {0}".format(cls.__name__))
        cls.engine = sqlalchemy.create_engine("sqlite:///test.db")
        meta.Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker()
        cls.Session.configure(bind=cls.engine)

    def setUp(self):
        """Called each time a test case is called,
        He we wrap the test case in Transaction Magic(TM)
        Meaning we can roll the test case back, returning the database to normal
        """
        connection = self.engine.connect()

        # Begin the Transaction
        self.transaction = connection.begin()

        # And bind the session
        self.session = self.Session(bind=connection)

    def tearDown(self):
        """
        Close the transaction and rollback after each test case is called
        """
        # testing.tearDown()
        self.transaction.rollback()
        self.session.close()


class ModelTestCase(BaseTestCase):
    """Subclass to test models

    Tests the inherited functionality that should be present in all models
    """

    def testEq(self):
        self.fail("You need to implement the Equality Test for this Model")

    def testCmp(self):
        self.fail("You need to implement the CMP test for this Model")

    def assertReallyEqual(self, a, b):
        # assertEqual first, because it will have a good message if the
        # assertion fails.
        self.assertEqual(a, b)
        self.assertEqual(b, a)
        self.assertTrue(a == b)
        self.assertTrue(b == a)
        self.assertFalse(a != b)
        self.assertFalse(b != a)

    def assertReallyNotEqual(self, a, b):
        # assertNotEqual first, because it will have a good message if the
        # assertion fails.
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, a)
        self.assertFalse(a == b)
        self.assertFalse(b == a)
        self.assertTrue(a != b)
        self.assertTrue(b != a)

    def _serialobj(self):
        """Helper method, return an object to serialise"""
        self.fail("You need to implement a serialObj method for this class")
        pass

    def _dictobj(self):
        """Helper method, return a dictionary representation of the _serialobj object"""
        self.fail("You need to implement a serialObj method for this class")
        pass

    def testSerialise(self):
        theObj = self._serialobj()

        # convert to dictionary
        # theDict = theObj.toDict()
        theDict = theObj.dict()
        # print(f"{theDict=}")
        # Convert Back
        newObj = models.newClsFromJSON(theDict)
        # print(f"{newObj.dict()=}")
        self.assertEqual(theObj, newObj)

    def testDict(self):
        """Test Conversion to a dictionary"""
        theItem = self._serialobj()
        theDict = self._dictobj()
        # now = datetime.datetime.utcnow()

        objDict = theItem.dict()
        self.assertIsInstance(objDict, dict)
        self.assertEqual(objDict, theDict)
