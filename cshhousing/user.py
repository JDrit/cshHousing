from ldap_conn import get_points_uidNumbers, get_active
import request
from room import get_room

def get_points(request, uid_number1, uid_number, room_number = None):
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
        points = get_points_uidNumbers([uid_number1, uid_number2], request)
        # if one of the user' current room is the given room
        if room_number and DBSession.query(User.uid_number).filter(and_(
            or_(User.uid_number == uid_number1, User.uid_number == uid_number2),
            User.current_room == room_number)).first():
            points += 0.5
    else:
        points = get_points_uidNumber(uid_number1, request)
        if room_number and DBSession.query(User.uid_number).filter(
                User.uid_number == uid_number1,
                User.current_room == room_number).first():
            points += 0.5
    return points

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

def remove_current_room(uid_number):
    """
    Deletes a user's current room assignment, which is used to
        assign housing points.
    Arguments:
        uid_number: the uid number of the user to delete their
            current room
    """
    DBSession.query(User).filter(User.uid_number == uid_number).update({'current_room': None})

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
    return get_active(request)

def create_current_room(uid_number, room_number):
    """
    Adds a current room assigment to the give user
    Arguments:
        uid_number: the uid number of the user being updated
        room_number: the room number of the current room assignment
    """
    DBSession.query(User).filter(
            User.uid_number == uid_number).update(
                    {'current_room': room_number}).first()

def get_user_names(uid_numbers, request):
    """
    Gets the usernames for the given uid numbers
    Arguments:
        uid_numbers: the list of uid numbers to get usernames for
        request: The HTTP request used to get settings from
    Returns the list of uid numbers with the associated usernames
    """
    return []
