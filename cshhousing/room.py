from sqlalchemy import or_, and_
from .models import DBSession, Room, User

def signup_for_room(room_number, id1, id2):
    """
    Tries to sign the given users up for the given room number. The new users
    will kick out the old residents if the new users have more housing points.
    Everyone is updated upon completion.
    Arguments:
        room_number: the room number to join
        id1: the uid number of the first roommate
        id2: the uid number of the second roomate
    Returns True if the join was successfull, False otherwise
    """
    return True

def admin_update_room(room_number, id1, id2, locked, single):
    """
    An admin updates a current room, ignoring anything about housing points.
    Arguments:
        room_number: the room number of the room to update
        id1: the uid number of the first resident
        id2: the uid number of the second resident
        locked: if the room should be locked
        single: if only one person is allowed to join the room
    """
    pass

def get_rooms():
    """
    Gets the list of valid room assignments
    Returns a list of all the rooms that users can sign up for
    """
    return []

def leave_room(uid_number):
    """
    The user leaves there current room assigment. If the user is in a room
    with their roommate, then that roommate is also removed
    Arguments:
        uid_number: the uid number of the user that is leaving
            there room
    Returns True if the removal was successful, False otherwise
    """
    return True
