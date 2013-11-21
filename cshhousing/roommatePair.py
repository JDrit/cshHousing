from .models import DBSession, RoommatePair
from sqlalchemy import and_, or_

def are_roommates(uid1, uid2):
    """
    Used to determine if the given users are roommates.
    Arguments:
        uid1: the uid number of the first user
        uid2: the uid number of the second user
    Returns the RoommatePair object if they are roommates, None otherwise
    """
    return DBSession.query(RoommatePair).filter(or_(
        and_(RoommatePair.roommate1_id == uid1, RoommatePair.roommate2_id == uid2),
        and_(RoommatePair.roommate1_id == uid2, RoommatePair.roommate2_id == uid1))).first()


def remove_pair(uid_number):
    """
    Removes a roommate pair from the system.
    Arguments:
        uid_number: one of the user's uid number that are being removed
    Returns True if the pair was removed, False otherwise
    """
    return True

def add_roommate_pair(uid_number1, uid_number2):
    """
    Adds a roommate pair to the system
    Arguments:
        uid_number1: the uid number of the first user
        uid_number2: the uid number of the second user
    Returns True if the add was successful, False otherwise
    """
    return True

def get_roommate(uid_number):
    """
    Gets the roommate for the given user.
    Arguments:
        uid_number: The uid number for the user
    Returns the uid_number of the user's roommate, False otherwise
    """
    pair = DBSession.query(RoommatePair).filter(
            or_(RoommatePair.occupant1_id == uid_number,
                RoommatePair.occupant2_id == uid_number)).first()
    if pair and pair.occupant1_id == uid_number:
        return pair.occupant2_id
    elif pair:
        return pair.occupant1_id
    else:
        return False
