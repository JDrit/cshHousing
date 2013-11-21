def get_points(uid_number1, uid_number2 = None, room_number = None):
    """
    Gets the points that the given users have.
    Arguments:
        uid_number1: the uid number for the first user
        uid_number2: the uid number for the second user
        room_number: the room number that the user are joining, used for
            squatters rights
    Returns the amount of housing points that the users have
    """
    return 0

def send_notification(uid_number):
    """
    Sends the notifications to users when there housing status changes
    Arguments:
        uid_number: the uid_number of the user to send a notification to
    Returns True if the notification was sent, False otherwise
    """
    return True

def update_user_info(uid_number, send_email = None, roommate_id = None):
    """
    Updates the user's information
    Arguments:
        uid_number: the uid_number of the user to update
        send_email: True if the user wants to recieve housing alerts
        roommate_id: the uid number of the user that the user wants to room with
    """
    pass

def remove_current_room(uid_number):
    """
    Deletes a user's current room assignment, which is used to assign housing points.
    Arguments:
        uid_number: the uid number of the user to delete their current room
    """
    pass

def is_admin(username):
    """
    Checks to see if the given user is can see the admin console or not
    Arguments:
        username: the username to check
    Returns True if the user is an admin, False otherwise
    """
    return True

def get_valid_users():
    """
    Gets the list of all the users that are allowed to signup on the housing board
    Returns a list of users, each one a tuple (uid number, uid, common name)
    """
    return []

def create_current_room(uid_number, room_number):
    """
    Adds a current room assigment to the give user
    Arguments:
        uid_number: the uid number of the user being updated
        room_number: the room number of the current room assignment
    """
    pass

def get_user_names(uid_numbers):
    """
    Gets the usernames for the given uid numbers
    Arguments:
        uid_numbers: the list of uid numbers to get usernames for
    Returns the list of uid numbers with the associated usernames
    """
    return []
