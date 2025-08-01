# from datetime import datetime
import datetime

# Python Module Imports
import cogent.base.model as models

from . import base

NOW = datetime.datetime.now(datetime.UTC)


class TestReading(base.ModelTestCase):
    def _serialobj(self):
        """Helper Method to provde an object to serialise"""
        theItem = models.Reading(time=NOW, nodeId=1, typeId=2, locationId=3, value=45.0)
        return theItem

    def _dictobj(self):
        """Helper method to provide a dictionay representaiton of the object
        generated by _serialobj()"""

        # REMEMEBR THAT Reading does some name trickery
        theDict = {
            "__table__": "Reading",
            "time": NOW.isoformat(),
            "nodeId": 1,
            "type": 2,
            "locationId": 3,
            "value": 45.0,
        }
        return theDict

    def testAdict(self):
        foo = self._serialobj()
        bar = self._dictobj()
        print()
        print("=" * 40)
        print("SERIAL {0}".format(foo))
        foo = foo.dict()
        print("SDICT {0}".format(foo))
        print("DICT {0}".format(bar))
        self.assertEqual(foo, bar)

    def testEq(self):
        """Test for Equality"""
        item1 = models.Reading(time=NOW, nodeId=1, typeId=2, locationId=3, value=45.0)

        item2 = models.Reading(time=NOW, nodeId=1, typeId=2, locationId=3, value=45.0)

        self.assertEqual(item1, item2)
        self.assertReallyEqual(item1, item2)

        # Or Location id
        item2.locationId = 10
        self.assertReallyEqual(item1, item2)

    def testNEQ(self):
        """Test for Inequality"""
        item1 = models.Reading(time=NOW, nodeId=1, typeId=2, locationId=3, value=45.0)

        item2 = models.Reading(time=NOW, nodeId=1, typeId=2, locationId=3, value=45.0)

        self.assertEqual(item1, item2)

        item2.time = datetime.datetime.now(datetime.UTC)
        self.assertReallyNotEqual(item1, item2)

        item2.time = item1.time
        item2.nodeId = 10
        self.assertReallyNotEqual(item1, item2)

        item2.nodeId = 1
        item2.typeId = 10
        self.assertReallyNotEqual(item1, item2)

        item2.locationId = 3
        item2.value = 0.0
        self.assertReallyNotEqual(item1, item2)

    def testCmp(self):
        #     """Test Compaison function
        #     (actually __lt__ for Py3K Comat)"""

        item1 = models.Reading(time=NOW, nodeId=1, typeId=2, locationId=3, value=45.0)

        item2 = models.Reading(time=NOW, nodeId=1, typeId=2, locationId=3, value=45.0)

        self.assertEqual(item1, item2)

        item2.time = datetime.datetime.now(datetime.UTC)
        self.assertGreater(item2, item1)

    #     item1 = models.Reading(id=1,
    #                         houseId = 2,
    #                         roomId = 3)

    #     item2 = models.Reading(id=1,
    #                         houseId = 2,
    #                         roomId = 3)

    #     self.assertEqual(item1,item2)

    #     #Order on HouseId
    #     item2.houseId = 1
    #     self.assertGreater(item1,item2)

    #     item2.houseId = 3
    #     self.assertLess(item1,item2)

    #     item2.houseId = 2

    #     #Order on HouseId
    #     item2.roomId = 1
    #     self.assertGreater(item1,item2)

    #     item2.roomId = 5
    #     self.assertLess(item1,item2)
