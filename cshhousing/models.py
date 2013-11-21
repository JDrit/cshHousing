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
    room_number = Column(Integer, primary_key = True)
    occupant_id1 = Column(Integer)
    occupant_id2 = Column(Integer)
    is_locked = Column(Boolean, default = False)
    housing_points = Column(Float, default = 0)
    is_single = Column(Boolean, default = False)

    def __init__(self, number, locked = False, single = False):
        self.room_number = number
        self.is_locked = locked
        self.is_single = single

    def __str__(self):
        return str(self.room_number) + ", " + str(self.occupant_id2) + ", " + str(self.occupant_id1)

class User(Base):
    """
    This stores information about a given user who is using the housing website
    name: the uid number of the user the information is about
    number: the current room number of that the user is in
    send: if the website should send notifications to the user
    roommate: another user that is allowed to control the user's housing status
    """
    __tablename__ = 'users'
    uid_number = Column(Integer, primary_key = True)
    current_room = Column(Integer)
    send_notifications = Column(Boolean, default = False)
    roommate_pair = relationship('RoommatePair')

    def __init__(self, number, room_number = None, send = False):
        self.uid_number = number
        self.current_room = room_number
        self.send_notifications = send

    def __str__(self):
        return "uid number: " + str(self.uid_number) + ", room: " + str(self.current_room)

class RoommatePair(Base):
    """
    This is used to show which users are roommates with each other
    roommate1_id: the uid number for the first roommate
    roommate2_id: the uid number for the second roommate
    """
    __tablename__ = 'roommates'
    id = Column(Integer, primary_key = True, autoincrement = True)
    roommate1_id = relationship(Integer, ForeignKey('User.uid_number'))
    roommate2_id = relationship(Integer, ForeignKey('User.uid_number'))

    def __init__(self, id1, id2):
        self.roommate1_id = id1
        self.roommate2_id = id2

class Log(Base):
    """
    The deletable logs that get displayed in the admin section
    index: a primary, autoincrementing integer
    date: the time the log event occurred
    uid_number: the uid number of the user that did the action
    log_type: the type of action that took place
    log_data: a description of the action
    status: True if the log message should be displayed, False otherwise
    """
    __tablename__ = 'logs'
    index = Column(Integer, primary_key = True, autoincrement = True)
    date = Column(DateTime, default = datetime.datetime.now())
    uid_number = Column(Integer)
    log_type = Column(Text)
    log_data = Column(Text)
    status = Column(Boolean, default = True)

    def __init__(self, uid_number, log_type, log_data):
        self.uid_number = uid_number
        self.log_type = log_type
        self.log_data = log_data

    def __str__(self):
        return str(self.date) + " : " + self.log_type + " : " + self.log_data
