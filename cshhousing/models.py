from sqlalchemy import Column, Integer, Text, Boolean, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import datetime

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
        self.points = 0

    def __str__(self):
        return str(self.number) + ", " + str(self.name1) + ", " + str(self.name2)

class User(Base):
    __tablename__ = 'users'
    name = Column(Integer, primary_key = True)
    number = Column(Integer)

    def __init__(self, name, number):
        self.name = name
        self.number = number

    def __str__(self):
        return str(self.name) + ", " + str(self.number)

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
