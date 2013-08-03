from sqlalchemy import (
    Column,
    Integer,
    Text,
    Boolean,
    )

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )

from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Room(Base):
    __tablename__ = 'rooms'
    number = Column(Integer, primary_key = True)
    name1 = Column(Integer)
    name2 = Column(Integer)
    locked = Column(Boolean)
    points = Column(Integer)

    def __init__(self, number):
        self.number = number

''''
class Page(Base):
    __tablename__ = 'pages'
    id = Column(Integer, primary_key = True)
    name = Column(Text, unique = True)
    data = Column(Text)

    def __init__(self, name, data):
        self.name = name
        self.data = data
'''
