# from datetime import datetime

# Python Module Imports


import cogent.base.model as models

from . import base


class TestLocation(base.ModelTestCase):
    def _serialobj(self):
        """Helper Method to provde an object to serialise"""
        theItem = models.Location(id=1, houseId=2, roomId=3)
        return theItem

    def _dictobj(self):
        """Helper method to provide a dictionay representaiton of the object
        generated by _serialobj()"""

        theDict = {
            "__table__": "Location",
            "id": 1,
            "houseId": 2,
            "roomId": 3,
        }
        return theDict

    def testEq(self):
        """Test for Equality"""
        item1 = models.Location(id=1, houseId=2, roomId=3)

        item2 = models.Location(id=1, houseId=2, roomId=3)

        self.assertEqual(item1, item2)
        self.assertReallyEqual(item1, item2)

        # Not massivly botherered about Id at the moment
        item2.id = 5
        self.assertEqual(item1, item2)
        self.assertReallyEqual(item1, item2)

    def testNEQ(self):
        item1 = models.Location(id=1, houseId=2, roomId=3)

        item2 = models.Location(id=1, houseId=2, roomId=3)

        self.assertEqual(item1, item2)

        item2.houseId = 10
        self.assertNotEqual(item1, item2)
        self.assertReallyNotEqual(item1, item2)

        item2.houseId = 2
        item2.roomId = 10
        self.assertNotEqual(item1, item2)
        self.assertReallyNotEqual(item1, item2)

    def testCmp(self):
        """Test Compaison function

        (actually __lt__ for Py3K Comat)"""

        item1 = models.Location(id=1, houseId=2, roomId=3)

        item2 = models.Location(id=1, houseId=2, roomId=3)

        self.assertEqual(item1, item2)

        # Order on HouseId
        item2.houseId = 1
        self.assertGreater(item1, item2)

        item2.houseId = 3
        self.assertLess(item1, item2)

        item2.houseId = 2

        # Order on HouseId
        item2.roomId = 1
        self.assertGreater(item1, item2)

        item2.roomId = 5
        self.assertLess(item1, item2)

        # Order on LocationId
        item1 = models.Location(id=1, houseId=2, roomId=3)

        item2 = models.Location(id=2, houseId=2, roomId=3)

        self.assertGreater(item2, item1)
        self.assertLess(item1, item2)
