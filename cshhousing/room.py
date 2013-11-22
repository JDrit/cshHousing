from sqlalchemy import or_, and_
from .models import DBSession, Room, User
import user
import roommatePair

def signup_for_room(room_number, id1, id2, request):
    """
    Tries to sign the given users up for the given room number. The new users
    will kick out the old residents if the new users have more housing points.
    Everyone is updated upon completion.
    Arguments:
        room_number: the room number to join
        id1: the uid number of the first roommate
        id2: the uid number of the second roomate, None if joining without a roommate
        request: the HTTP request object used to get the settings from
    Returns True if the join was successfull, False otherwise
    """
    room = DBSession.query(Room).filter(Room.room_number == room_number).first()

    if room.locked: # if the room is locked
        return False
    if not roommatePair.are_roommates(id1, id2): # if the users are not roomates
        return False
    # if the user is already in another room
    if DBSession.query(Room).filter(or_(Room.occupant1 == id1, Room.occupant2 == id1)).first():
        return False
    if id1 == id2: # cannot join with yourself
        return False
    if room.single and id2: # can only join single alone
        return False

    new_points = user.get_points(request, id1, id2, room_number)
    old_points = user.get_points(request, room.occupant1, room.occupant2, room_number)
    if new_points > old_points:
        user.send_notification(room.occupant1, "You have been kicked from room " + str(room.room_number), request)
        user.send_notification(room.occupant2, "You have been kicked from room " + str(room.room_number), request)
        user.send_notification(id1, "You have joined room " + str(room.room_number), request)
        user.send_notification(id2, "You have joined room " + str(room.room_number), request)
        room.occupant1 = id1
        room.occupant2 = id2
        DBSession.add(room)

        return True
    else:
        return False

def admin_update_room(room_number, id1, id2, locked, single, request):
    """
    An admin updates a current room, ignoring anything about housing points.
    Arguments:
        room_number: the room number of the room to update
        id1: the uid number of the first resident
        id2: the uid number of the second resident
        locked: if the room should be locked
        single: if only one person is allowed to join the room
        request: the HTTP request used to get the settings from
    """
    DBSession.query(Room).filter(Room.room_number == room_number).update(
            {'occupant1': id1, 'occupant2': id2,
                'locked': locked, 'single': single,
                'housing_points': user.get_points()}).first()

def prepare_rooms_for_html(request):
    """
    Gets all the rooms to be used to display and adds the usernames
    for the occupants to the objects
    Arguments:
        request: the HTML request object used to get the LDAP settings
    Returns the rooms with the usernames and points added to it
    """
    rooms = DBSession.query(Room).all()
    uid_numbers = []
    for room in rooms:
        if room.occupant1:
            setattr(room, 'name1', ldap_conn.get_username(room.occupant1))
            uid_numbers.append(room.occupant1)
        if room.occupant2:
            setattr(room, 'name2', ldap_conn.get_username(room.occupant2))
            uid_numbers.append(room.occupant2)
        setattr(room, 'points', ldap_conn.get_points_uidNumbers(uid_numbers, request))
    return rooms

def get_rooms():
    """
    Gets the list of valid room assignments
    Returns a list of all the rooms that users can sign up for
    """
    return DBSession.query(Room).all()

def get_room(room_number):
    """
    Gets the room object at the given room number
    Arguments:
        room_number: the room number of the room to get
    Returns the room object or None
    """
    return DBSession.query(Room).filter(Room.room_number == room_number).first()

def get_valid_rooms():
    numbers = []
    numbers_validate = []
    for room in get_rooms():
        numbers.append((room.number, room.number))
        numers.validate.append(room.number)
    return numbers, numbers_validate


def get_users_room(uid_number):
    """
    Gets the room that the user is signed up for
    Arguments:
        uid_number: the uid number of the given user
    Returns the room object, or None
    """
    return DBSession.query(Room).filter(or_(Room.occupant1_id == uid_number,
        Room.occupant2_id == uid_number)).first()

def leave_room(uid_number):
    """
    The user leaves there current room assigment. If the user is in a room
    with their roommate, then that roommate is also removed
    Arguments:
        uid_number: the uid number of the user that is leaving
            there room
    Returns True if the removal was successful, False otherwise
    """
    room = DBSession.query(Room).filter(or_(Room.occupant1 == uid_number,
        Room.occupant2 == uid_number)).first()
    if room.occupant1 == uid_number:
        room.occupant1 = None
    else:
        room.occupant2 = None
    DBSession.add(room)
    log.add_log(uid_number, "leave", "user left room #" + room.room_number)
