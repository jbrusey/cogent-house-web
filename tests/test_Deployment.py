"""
Testing for the Deployment Module

:author: Dan Goldsmith <djgoldsmith@googlemail.com>
"""

# from datetime import datetime
import datetime
import logging

# Python Module Imports
import cogent.base.model as models

from . import base

log = logging.getLogger(__name__)


# Global Timestamp
NOW = datetime.datetime.now(datetime.UTC)


class TestDeployment(base.ModelTestCase):
    """
    Deal with tables in the deployment module
    """

    # GENERAL TESTS
    def testCreate(self):
        """Can we Create Deployments"""
        thisDeployment = models.Deployment()
        self.assertIsInstance(thisDeployment, models.Deployment)

        thisDeployment = models.Deployment(description="Test")
        self.assertEqual(thisDeployment.description, "Test")

    def _serialobj(self):
        """Helper Method to provde an object to serialise"""

        theItem = models.Deployment(
            id=1,
            name="Test",
            description="A Testing Deployment",
            startDate=NOW,
            endDate=NOW,
        )

        return theItem

    def _dictobj(self):
        """Helper method to provide a dictionay representaiton of the object generated by
        _serialobj()"""
        theDict = {
            "__table__": "Deployment",
            "id": 1,
            "name": "Test",
            "description": "A Testing Deployment",
            "startDate": NOW.isoformat(),
            "endDate": NOW.isoformat(),
        }

        return theDict

    def testEq(self):
        """Test for Equality"""
        # Test Equality
        item1 = models.Deployment(id=1, name="Test Deployment")
        item2 = models.Deployment(id=1, name="Test Deployment")
        self.assertEqual(item1, item2)
        self.assertReallyEqual(item1, item2)

        # And In Equality
        item2 = models.Deployment(id=1, name="Test DeploymentA")
        self.assertNotEqual(item1, item2)
        self.assertReallyNotEqual(item1, item2)

    def testCmp(self):
        # Test Comparator
        item1 = models.Deployment(id=1, name="Test")
        item2 = models.Deployment(id=1, name="Test")

        self.assertEqual(item1, item2)

        item2 = models.Deployment(id=1, name="A_Test")
        self.assertGreater(item1, item2)

        item2 = models.Deployment(id=1, name="Z_Test")
        item2.id = 2
        self.assertLess(item1, item2)

    def testJSON(self):
        # Does this return the expected JSON representaion

        item = models.Deployment(
            id=1,
            name="Test",
        )

        basedict = {
            "__table__": "Deployment",
            "id": 1,
            "name": "Test",
            "description": None,
            "startDate": None,
            "endDate": None,
        }

        itemdict = item.dict()
        self.assertEqual(basedict, itemdict)
        # item = models.Deployment(id=42,
        #                          name="foobar",
        #                          )

        # basedict = {"id":"D_42",
        #             "name":"foobar",
        #             "label":"foobar",
        #             "type":"deployment",
        #             "children":[],
        #             "parent":"root"}

        # itemdict = item.asJSON()

        # self.assertEqual(basedict,itemdict)
