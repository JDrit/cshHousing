from .models import DBSession, Log

def clear_logs(uid_number):
    """
    Marks all the logs are cleared, setting their status to False
    Arguments:
        uid_number: the uid number of the user that cleared the logs
    """
    DBSession.query(Log).filter(Log.status == True).update({'status': False})
    add_log(uid_number, "cleared logs", "Cleared the logs")

def add_log(uid_number, reason, info):
    """
    Adds a new log to the database
    Arguments:
        uid_number: the uid number of the user that did the action
        reason: the type of action
        info: the description of the action
    """
    DBSession.add(Log(uid_number, reason, info))

def get_logs():
    """
    Gets all the active logs for the system
    """
    return DBSession.query(Log).filter(Log.status == True
            ).order_by(Log.index.desc()).all()
