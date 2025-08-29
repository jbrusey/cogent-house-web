# from distutils.core import setup
import os
import sys

from setuptools import setup  # type: ignore[import-untyped]

# Fix for when a virtualenv is used to install
here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, "CHANGES.txt")).read()
CHANGES = open(os.path.join(here, "CHANGES.txt")).read()

# calculate the prefix to install data files into to meet debian FHS
if sys.prefix == "/usr":
    conf_prefix = ""  # If its a standard "global" instalation
else:
    conf_prefix = "{0}/".format(sys.prefix)


REQUIRES = [
    "SQLAlchemy",
    "mysqlclient",
    "configobj",
    "python-dateutil>=1.5",
    "numpy",
    "matplotlib",
    "pyserial",
    "requests",
    "transaction",
    "alembic",
]

setup(
    name="ch-web",
    version="1.2",
    description="CogentHouse base station logger",
    author="James Brusey, Ross Wilkins, Dan Goldsmith",
    author_email="james.brusey@gmail.com",
    packages=[
        "cogent",
        "cogent.base",
        "cogent.base.model",
        "cogent.report",
        "cogent.sip",
        "cogent.scripts",
        "cogent.alembic",
    ],
    include_package_data=True,
    entry_points="""\
      [console_scripts]
      initialize_cogent_db = cogent.scripts.initializedb:main
      """,
    install_requires=REQUIRES,
)
