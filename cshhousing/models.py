from sqlalchemy import Column, Integer, Text, Boolean, DateTime, Date, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import datetime

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Room(Base):
    """
    This stores information on the actual rooms that are available
    number: the room's number
    name1: the uidNumber of the first ocupant
    name2: the uidNumber of the seconds ocupant
    locked: boolean if the room is locked so no one can sign up for it
    points: the number of points the current ocupants have
    single: if the room only allows one ocupant
    """
    __tablename__ = 'rooms'
    number = Column(Integer, primary_key = True)
    name1 = Column(Integer)
    name2 = Column(Integer)
    locked = Column(Boolean, default = False)
    points = Column(Float, default = 0)
    single = Column(Boolean, default = False)

    def __init__(self, number, locked = False, single = False):
        self.number = number
        self.locked = locked
        self.single = single

    def __str__(self):
        return str(self.number) + ", " + str(self.name1) + ", " + str(self.name2)

class User(Base):
    __tablename__ = 'users'
    name = Column(Integer, primary_key = True)
    number = Column(Integer)
    send = Column(Boolean)

    def __init__(self, name, number = None, send = False):
        self.name = name
        self.number = number
        self.send = False

    def __str__(self):
        return str(self.name) + ", " + str(self.number) + ", " + str(self.send)

class Log(Base):
    __tablename__ = 'logs'
    index = Column(Integer, primary_key = True, autoincrement = True)
    date = Column(DateTime, default = datetime.datetime.now())
    uid_number = Column(Integer)
    log_type = Column(Text)
    log_data = Column(Text)

    def __init__(self, uid_number, log_type, log_data):
        self.uid_number = uid_number
        self.log_type = log_type
        self.log_data = log_data

    def __str__(self):
        return str(self.date) + " : " + self.log_type + " : " + self.log_data
