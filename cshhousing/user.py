import ldap_conn
import request
import room
from .models import DBSession, Room, User

def get_user(uid_number):
    """
    Gets the User object for the given user id
    Arguments:
        uid_number: the uid number to search by
    Returns the User object or None
    """
    return DBSession.query(User).filter(User.uid_number == uid_number).first()

def get_points(request, uid_number1, uid_number = None, room_number = None):
    """
    Gets the points that the given users have.
    Arguments:
        request: the request object used to get settings for LDAP
        uid_number1: the uid number for the first user
        uid_number2: the uid number for the second user
        room_number: the room number that the user are joining, used for
            squatters rights
    Returns the amount of housing points that the users have
    """
    if uid_numbers2:
        points = ldap_conn.get_points_uidNumbers([uid_number1, uid_number2], request)
        # if one of the user' current room is the given room
        if room_number and DBSession.query(User.uid_number).filter(and_(
            or_(User.uid_number == uid_number1, User.uid_number == uid_number2),
            User.current_room == room_number)).first():
            points += 0.5
    else:
        points = ldap_conn.get_points_uidNumber(uid_number1, request)
        if room_number and DBSession.query(User.uid_number).filter(
                User.uid_number == uid_number1,
                User.current_room == room_number).first():
            points += 0.5
    return points

def get_send_status(uid_number):
    """
    Returns if the user wants to have notifications sent to him
    Arguments:
        uid_number: the uid number of the user
    Returns True if the user wants to recieve notifications, False otherwise
    """
    return DBSession.query(User.send_notifications).filter(User.uid_number == uid_number).first()[0]

def send_notification(uid_number, message, request):
    """
    Sends the notifications to users when there housing status changes
    Arguments:
        uid_number: the uid_number of the user to send a notification to
        message: the message to send
        request: the http request object used to get the setting informations
    Returns True if the notification was sent, False otherwise
    """
    if DBSession.query(User.send_notifications).filter(User.uid_number == uid_number).first():
        useraname = ldap.get_usernam
        username = ldap.get_username(uid_number)
        requests.get("https://www.csh.rit.edu/~kdolan/notify/apiDridge.php?username=" +
                username + "&notification=" +
                message.replace(" ", "&") + "&apiKey=" +
                request.registry.settings['api_key'],
                verify = False)
        return True
    else:
        return False

def update_user_info(uid_number, send_email = None,
        roommate_id = None):
    """
    Updates the user's information
    Arguments:
        uid_number: the uid_number of the user to update
        send_email: True if the user wants to recieve housing
            alerts
        roommate_id: the uid number of the user that the user
            wants to room with
    """
    if send_email:
        DBSession.query(User).filter(User.uid_number == uid_number).update({'send_notifications': send_email}).first()

def remove_current_room(username, uid_number):
    """
    Deletes a user's current room assignment, which is used to
        assign housing points.
    Arguments:
        username: the username of the admin who did the deletation
        uid_number: the uid number of the user to delete their current room
    """
    DBSession.query(User).filter(User.uid_number == uid_number).update({'current_room': None})
    room.update_room_points(uid_number)
    log.add_log(ldap_con.get_uid_number(username), "delete current", "Deleted " + str(uid_number) + "'s current room")

def is_admin(username):
    """
    Checks to see if the given user is can see the admin console
    or not
    Arguments:
        username: the username to check
    Returns True if the user is an admin, False otherwise
    """
    return username == 'jd' or username == 'keller'

def get_valid_users(request):
    """
    Gets the list of all the users that are allowed to signup on the housing board
    Arguments:
        request: the HTTP request object used to get settings
    Returns a list of users, each one a tuple (uid number, uid, common name)
    """
    return ldap_conn.get_active(request)

def get_valid_roommates(uid):
    """
    Gets the information needed on what members are valid roommates.
    Arguments:
        uid: the username of the user who is asking for roommates
    Returns (names, names_validate)
        names: the list of the text to display for the names
        names_validate: the list of the valid uid_numbers
    """
    names = []
    names_validate = []
    for pair in ldap_conn.get_active(request):
            if not pair[1] == uid:
                names.append((pair[0], pair[2] + " - " + pair[1]))
                names_validate.append(pair[0])
    return names, names_validate


def create_current_room(uid_number, room_number):
    """
    Adds a current room assigment to the give user
    Arguments:
        uid_number: the uid number of the user being updated
        room_number: the room number of the current room assignment
    """
    user = DBSession.query(User).filter(User.uid_number == uid_number).first()
    if user:
        user.current_room = room_number
    else:
        user = User(uid_number, room_number = room_number)
    DBSession.add(user)

def get_user_names(uid_numbers, request):
    """
    Gets the usernames for the given uid numbers
    Arguments:
        uid_numbers: the list of uid numbers to get usernames for
        request: The HTTP request used to get settings from
    Returns the list of uid numbers with the associated usernames
    """
    return []

def get_current_room(uid_number):
    """
    Gets the room number of the user's current room.
    Arguments:
        uid_number: the uid number of the user
    Returns int of the room number
    """
    result = DBSession.query(User.current_room).filter(User.uid_number == uid_number).first()
    if result[0]:
        return result[0]
    else:
        return None
