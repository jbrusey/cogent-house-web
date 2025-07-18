"""
.. codeauthor::  Ross Wilkins
.. codeauthor::  James Brusey
.. codeauthor::  Daniel Goldsmith <djgoldsmith@googlemail.com>
"""

from sqlalchemy import Column, Float, ForeignKey, Integer, String

from . import meta


class HouseMetadata(meta.Base, meta.InnoDBMix):
    """Table to hold Metadata about houses

    :var Integer id: id
    :var Integer houseId: *foreignKey* Id of
        :class:`cogentviewer.models.house.House` this belongs to

    :var string name: Name of metadata
    :var string description: Description of metadata
    :var string units: Units of Metadata
    :var float value: Value of metadata

    """

    __tablename__ = "HouseMetadata"

    id = Column(Integer, primary_key=True)
    houseId = Column(Integer, ForeignKey("House.id"))
    name = Column(String(255))
    description = Column(String(255))
    units = Column(String(20))
    value = Column(Float)
