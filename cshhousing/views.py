import re
import colander
import deform_bootstrap
import deform
import ldap_conn
import datetime
import transaction
from docutils.core import publish_parts
from pkg_resources import resource_filename
from deform_bootstrap.widget import ChosenSingleWidget, DateTimeInputWidget
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.view import view_config
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import or_, and_
from .models import DBSession, Room, User, Log, Final_Log
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer
from translationstring import TranslationStringFactory
from ldap_conn import *
from datetime import datetime
from threading import Timer
import subprocess
import requests

_ = TranslationStringFactory('deform')
css = HtmlFormatter().get_style_defs('.highlight')

site_closed = False # boolean used to determine if users can modify the layout
close_time = None   # the time to auto close the site
open_time = None    # the time that the site will auto open
lock_thread = None  # this is the thread that will lock the site at a given time
open_thread = None  # this is the thread that will open the site at a given time

class Time_Exception(Exception):
    # used for seeing if the admin times for opening and closing are correct
    pass


def lock_site():
    """
    This is the function that is run as a delay to lock the site at a given time
    """
    global site_closed
    site_closed = True

def unlock_site():
    global site_closed
    site_closed = False

def add_log(uid_number, reason, info):
    DBSession.add(Log(uid_number, reason, info))
    DBSession.add(Final_Log(uid_number, reason, info))

def send_notification(uid, message, request):
    uid_number = get_uid_number(uid, request)
    user = DBSession.query(User).filter_by(name = uid_number).first()
    if user and user.send:
        requests.get("https://www.csh.rit.edu/~kdolan/notify/apiBridge.php?username="
        + uid + "&notification=" + message.replace(" ", "+") + "&apiKey=" +
        request.registry.settings['api_key'], verify = False)

def translator(term):
    return get_localizer(get_current_request()).translate(term)
    deform_template_dir = resource_filename('deform', 'templates/')
    zpt_renderer = deform.ZPTRendererFactory(
                [deform_template_dir], translator=translator)

@view_config(context=HTTPNotFound, renderer='templates/404.pt')
def view_404(request):
    global site_closed
    admin = isEBoard(request.headers['X-Webauth-User'], request)
    uid_number = get_uid_number(request.headers['X-Webauth-User'], request)
    return {'admin': admin, 'locked': site_closed,
            'next_room': DBSession.query(Room).filter(or_(
                Room.name1 == uid_number, Room.name2 == uid_number)).first()}

@view_config(route_name='view_settings', renderer='templates/settings.pt')
def view_settings(request):
    global site_closed
    msg = None
    names = []
    names_validate = []
    uid = request.headers['X-Webauth-User']
    uid_number = get_uid_number(uid, request)
    admin = isEBoard(request.headers['X-Webauth-User'], request)
    none = 'none'
    names.append((none, '- None -'))
    names_validate.append(none)

    for pair in get_active(request):
        if not pair[1] == uid:
            names.append((pair[0], pair[2] + " - " + pair[1]))
            names_validate.append(pair[0])

    uid_number = get_uid_number(request.headers['X-Webauth-User'], request)
    query = DBSession.query(User).filter_by(name = uid_number).first()
    status = False if not query else query.send

    class Schema(colander.Schema):
        send_email = colander.SchemaNode(
                colander.Bool(),
                title = 'Send Email',
                description = 'This will send emails to your CSH account when changes occur to your housing status',
                widget = deform.widget.CheckboxWidget(),
                default = status)
        roommate = colander.SchemaNode(
                colander.String(),
                title='Roommate\'s name',
                widget=ChosenSingleWidget(values=names),
                validator=colander.OneOf(names_validate),
                missing=None,
                description = 'You need to set this to whoever you want to be roommates with so that your they will be able to control your housing status. If you do not do this, then no one will be able to sign you up with them',
                default = query.roommate if query and query.roommate else none)


    form = deform.Form(Schema(), buttons = ('submit', 'cancel'))
    form_render = form.render()
    if ('submit', u'submit') in request.POST.items():
        try:
            appstruct = form.validate(request.POST.items())
            if not query:
                DBSession.add(User(uid_number, send = appstruct['send_email']))
            else:
                DBSession.query(User).filter_by(name = uid_number).update(
                        {'send': appstruct['send_email'],
                            'roommate': int(appstruct['roommate']) if appstruct['roommate'] != none else None})
            status = appstruct['send_email']
            msg = 'Your user settings have been updated'

            class Schema(colander.Schema):
                send_email = colander.SchemaNode(
                        colander.Bool(),
                        title = 'Send Email',
                        description = 'This will send emails to your CSH account when changes occur to your housing status',
                        widget = deform.widget.CheckboxWidget(),
                        default = status)
                roommate = colander.SchemaNode(
                        colander.String(),
                        title='Roommate\'s name',
                        widget=ChosenSingleWidget(values=names),
                        validator=colander.OneOf(names_validate),
                        missing=None,
                        description = 'This person will be able to change your housing status' +
                        'for you. Select the person you want to room with so that they can select a room for you',
                        default = int(appstruct['roommate']) if appstruct['roommate'] != none else none)


            form_render = deform.Form(Schema(), buttons=('submit', 'cancel')).render()
            transaction.commit()
        except deform.ValidationFailure, e:
            form_render = e.render()
    next_room = DBSession.query(Room).filter(or_(
        Room.name1 == uid_number, Room.name2 == uid_number)).first()
    return {'admin': admin, 'form': form_render, 'msg': msg,
            'locked': site_closed, 'next_room': next_room}


@view_config(route_name='view_delete_logs')
def view_delete_logs(request):
    settings = request.registry.settings
    if isEBoard(request.headers['X-Webauth-User'], request):
        DBSession.query(Log).delete()
        transaction.commit()
        request.session.flash("Logs cleared")
        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_delete_current')
def view_delete_current(request):
    settings = request.registry.settings
    conn = ldap_conn(request)

    if isEBoard(request.headers['X-Webauth-User'], request):
        try:
            user = DBSession.query(User).filter_by(name = request.matchdict['name']).one()
            DBSession.delete(user)

            room = DBSession.query(Room).filter(or_(Room.name1 == int(request.matchdict['name']), Room.name2 == int(request.matchdict['name']))).first()
            if room != None:
                room.points = sum(get_points_uidNumbers([room.name1, room.name2], request).values())
                if not DBSession.query(User).filter(or_( # squatting points
                    and_(User.name == room.name1, User.number == room.number),
                    and_(User.name == room.name2, User.number == room.number)
                    )).first() == None:
                    room.points += .5
                DBSession.add(room)
            request.session.flash("Successfully deleated current room assignment")
            result = conn.search("uidNumber=" + request.matchdict['name'])
            uid = result[0][0][1]['uid'][0] + "(" + str(request.matchdict['name']) + ")" if result != [] else str(request.matchdict['name'])
            add_log(get_uid_number(request.headers['X-Webauth-User'], request), "delete current", uid + "'s current room was deleted")
        except NoResultFound, e:
            request.session.flash("Warning: could not delete current room assignment")
        conn.close()
        return HTTPFound(request.route_url('view_admin'))
    else:
        conn.close()
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_admin', renderer='templates/admin.pt')
def view_admin(request):
    global site_closed, close_time, lock_thread, open_thread, open_time
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    conn = ldap_conn(request)
    uid_number = get_uid_number(request.headers['X-Webauth-User'], request)

    if isEBoard(request.headers['X-Webauth-User'], request):
        rooms = DBSession.query(Room).order_by(Room.number).all()
        room_numbers = set() # used to verify that same room # are not being used
        name_map = dict()
        points_map = dict()
        ids = set()
        for room in rooms:
            numbers.append((room.number, room.number))
            numbers_validate.append(room.number)
            room_numbers.add(room.number)
            if room.name1 is not None:
                ids.add(room.name1)
            if room.name2 is not None:
                ids.add(room.name2)

        for pair in get_active(request):
            names.append((pair[0], pair[1] + " - " + pair[2]))
            names_validate.append(pair[0])

        class NewRoomate(colander.Schema):
            username = colander.SchemaNode(
                    colander.String(),
                    title = 'Username',
                    widget = ChosenSingleWidget(values = names),
                    validator = colander.OneOf(names_validate),
                    missing = colander.required)
            roommate = colander.SchemaNode(
                    colander.String(),
                    title = 'Roommate\'s name',
                    widget = ChosenSingleWidget(values = names),
                    validator = colander.OneOf(names_validate),
                    missing = colander.required)

        class New_Room(colander.Schema):
            number = colander.SchemaNode(colander.Integer(),
                    missing = colander.required,
                    validator = colander.Function(
                        lambda value: not value in room_numbers))
            locked = colander.SchemaNode(colander.Bool())
            single = colander.SchemaNode(colander.Bool())

        class New_Rooms(colander.SequenceSchema):
            new_room = New_Room()

        class New_Rooms_Schema(colander.Schema):
            new_rooms = New_Rooms()

        class Current_Room(colander.Schema):
            name = colander.SchemaNode(colander.Integer())

        class Current_Room(colander.Schema):
            name = colander.SchemaNode(
                    colander.String(),
                    title = 'Member\'s Name',
                    widget = ChosenSingleWidget(values = names),
                    validator = colander.OneOf(names_validate),
                    missing = colander.required)
            number = colander.SchemaNode(
                    colander.Integer(),
                    title = 'Room Number',
                    widget = ChosenSingleWidget(values = numbers),
                    validator = colander.OneOf(numbers_validate),
                    missing = colander.required)

        class Current_Rooms(colander.SequenceSchema):
            current_room = Current_Room()

        class Current_Rooms_Schema(colander.Schema):
            current_rooms = Current_Rooms()

        class Time_Schema(colander.Schema):
            lock = colander.SchemaNode(
                    colander.Boolean(),
                    missing = colander.required,
                    default = site_closed,
                    description = "Locks the site so no users can change their status")
            open_time = colander.SchemaNode(
                    colander.DateTime(),
                    widget = DateTimeInputWidget(),
                    missing = None,
                    default = open_time,
                    description = "Auto opens the site at the given time")
            close_time = colander.SchemaNode(
                    colander.DateTime(),
                    widget = DateTimeInputWidget(),
                    missing = None,
                    default = close_time,
                    description = "Auto closes the site at a given time")

        roommate_form = deform.Form(NewRoomate(), buttons=('submit',))

        schema = New_Rooms_Schema()
        form = deform.Form(schema, buttons=('submit',))
        form['new_rooms'].widget = deform.widget.SequenceWidget(min_len=1)
        form_render = form.render()
        current_rooms_schema = Current_Rooms_Schema()
        current_rooms_form = deform.Form(current_rooms_schema, buttons=('submit',))
        current_rooms_form_render = current_rooms_form.render()
        time_set = deform.Form(Time_Schema(), buttons=('submit',))
        msgs = request.session.pop_flash()
        print request.POST
        if request.method == 'POST':
            if 'remove_roommate' in [item[0] for item in request.POST.items()]:
                user_id = request.POST.get('remove_roommate')
                user = DBSession.query(User).filter(User.name == user_id).first()
                if user:
                    user.roommate = None
                    DBSession.add(user)
                    msgs.append('Successfully removed user\'s roommate')
            # new room was given
            elif ('__start__', u'new_rooms:sequence') in request.POST.items():
                try:
                    appstruct = form.validate(request.POST.items())
                    rooms_added = 0
                    for new_room in appstruct['new_rooms']:
                        if not new_room['number'] in room_numbers:
                            room = Room(new_room['number'], new_room['locked'], new_room['single'])
                            DBSession.add(room)
                            room_numbers.add(new_room['number'])
                            rooms_added += 1
                            add_log(uid_number, "new room added",
                                    "added room #" + str(new_room['number']))
                            rooms.append(room)
                    rooms.sort(key = lambda room: room.number)
                    if len(appstruct['new_rooms']) > 1:
                        msgs.append('Successfully added ' + str(rooms_added) +
                                ' new rooms')
                    else:
                        msgs.append('Successfully added the new room')

                except deform.ValidationFailure, e:
                    msgs.append('Warning: could not added new rooms')
                    form_render = e.render()

            # current room was given
            elif ('__start__', u'current_rooms:sequence') in request.POST.items():
                try:
                    appstruct = current_rooms_form.validate(request.POST.items())
                    rooms_added = 0
                    for current_room in appstruct['current_rooms']:
                        # if the user does not exist yet
                        if DBSession.query(User).filter_by(
                                name = current_room['name']).update(
                                        {'number': current_room['number']}) == 0:
                            user = User(current_room['name'], current_room['number'])
                            DBSession.add(user)
                            rooms_added += 1
                            add_log(uid_number, "current room added",
                                    "added room #" + str(current_room['number']))
                        room = DBSession.query(Room).filter(
                                or_(Room.name1 == current_room['name'],
                                    Room.name2 == current_room['name'])).first()
                        if room != None:
                            room.points = sum(
                                    get_points_uidNumbers([room.name1, room.name2], request).values())
                            if not DBSession.query(User).filter(or_( # squatting points
                                and_(User.name == room.name1, User.number == room.number),
                                and_(User.name == room.name2, User.number == room.number)
                                )).first() == None:
                                room.points += .5
                            DBSession.add(room)
                    if len(appstruct['current_rooms']) == 1:
                        msgs.append('Successfully added current room')
                    else:
                        msgs.append('Successfully added current rooms')
                except deform.ValidationFailure, e:
                    msgs.append('Warning: Could not add current room assignment')
                    current_rooms_form_render = e.render()
            # settings were given
            elif ('__start__', u'close_time:mapping') in request.POST.items():
                try:
                    appstruct = time_set.validate(request.POST.items())
                    ct = appstruct.get('close_time', None)
                    ot = appstruct.get('open_time', None)
                    if ct != None and ct.replace(tzinfo=None) < datetime.now():
                        raise Time_Exception ("Invalid close time")
                    if ot != None and ot.replace(tzinfo=None) < datetime.now():
                        raise Time_Exception ("Invalid open time")
                    if ct != None and ot != None and ct.replace(tzinfo=None) < ot.replace(tzinfo=None):
                        raise Time_Exception ("Close time cannot be before the open time")

                    site_closed = bool(appstruct.get('lock', False))
                    close_time = ct
                    open_time = ot

                    if lock_thread != None:
                        lock_thread.cancel()
                    if open_thread != None:
                        open_thread.cancel()
                    if close_time != None:
                        lock_thread = Timer((close_time.replace(tzinfo=None) -
                            datetime.now()).seconds, lock_site)
                        lock_thread.start()
                        add_log(uid_number, "lock", "site will close at "  + str(close_time))
                        msgs.append("Site will close at " + str(close_time))
                    if open_time != None:
                        open_thread = Timer((open_time.replace(tzinfo=None) -
                            datetime.now()).seconds, unlock_site)
                        open_thread.start()
                        add_log(uid_number, "lock", "site will now open at " + str(open_time))
                        msgs.append("Site will open at " + str(open_time))
                    if site_closed:
                        add_log(uid_number, "lock", "site was closed")
                        msgs.append("Site is now closed")
                    else:
                        add_log(uid_number, "lock", "site was opened")
                        msgs.append("Site is now open")
                except deform.ValidationFailure, e:
                    msgs.append('Warning: Could not parse time inputs')
                except Time_Exception, e:
                    msgs.append("Warning: " + str(e))
            else:
                try:
                    appstruct = roommate_form.validate(request.POST.items())
                    if appstruct['username'] != appstruct['roommate']:
                        user = DBSession.query(User).filter(User.name == int(appstruct['username'])).first()
                        if user:
                            user.roommate = int(appstruct['roommate'])
                            DBSession.add(user)
                        else:
                            user = User(name = int(appstruct['username']), roommate = int(appstruct['roommate']))
                            DBSession.add(user)

                        msgs.append('Successfully updaed roommate pairs')
                    else:
                        msgs.append('Warning: People cannot room with themselves')
                except deform.ValidationFailure, e:
                    msgs.append('Warning: Could not parse input')

        logs = DBSession.query(Log).order_by(Log.index.desc()).limit(100).all()
        users = DBSession.query(User).all()
        for user in users:
            ids.add(user.name)
            ids.add(user.roommate)
        for log in logs:
            ids.add(log.uid_number)
        if not ids == set():
            for user in conn.search_uid_numbers(list(ids)):
                name_map[int(user[0][1]['uidNumber'][0])] = user[0][1]['uid'][0]
                points_map[int(user[0][1]['uidNumber'][0])] = int(user[0][1].get('housingPoints', [0])[0])

        next_room = DBSession.query(Room).filter(or_(
            Room.name1 == uid_number, Room.name2 == uid_number)).first()
        conn.close()
        return {'name_map': name_map, 'rooms': rooms, 'form': form_render, 'users': users,
                'points_map': points_map, 'current_rooms_form': current_rooms_form_render,
                'msgs': msgs, 'locked': site_closed, 'next_room': next_room, 'logs': logs,
                'time': time_set.render(), 'roommate_renderer': roommate_form.render()}
    else:
        conn.close()
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_admin_edit', renderer='templates/edit.pt')
def view_admin_edit(request):
    global site_closed
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    number_to_username = {} # dictionary used to convert uid number to username
    empty = 'empty'
    next_room = None
    uid_number = get_uid_number(request.headers['X-Webauth-User'], request)
    # any input that is not an actual number
    if not request.matchdict['room_number'].isdigit():
        request.session.flash("Warning: STOP FUCKING WITH MY SYSTEM")
        return HTTPFound(location = request.route_url('view_admin'))

    if isEBoard(request.headers['X-Webauth-User'], request):

        if ('cancel', u'cancel') in request.POST.items():
            return HTTPFound(location=request.route_url('view_admin'))
        found_room = False
        rooms = DBSession.query(Room).order_by(Room.number).all()
        for r in rooms:
            if str(r.number) == request.matchdict['room_number']:
                room = r
                found_room = True
            if uid_number == r.name1 or uid_number == r.name2:
                next_room = r
        if found_room != True:
            request.session.flash("Warning: Invalid room number")
            return HTTPFound(location=request.route_url('view_admin'))

        names.append((empty, '- Empty -'))
        names_validate.append(empty)
        for pair in get_active(request):
            names.append((pair[0], pair[2] + " - " + pair[1]))
            names_validate.append(pair[0])
            number_to_username[pair[0]] = pair[1]

        class Schema(colander.Schema):
            name1 = colander.SchemaNode(
		    	colander.String(),
			    title = 'Roommate #1',
    			widget = ChosenSingleWidget(values=names),
	    		validator = colander.OneOf(names_validate),
                default = room.name1 or empty,
                missing = None)
            name2 = colander.SchemaNode(
	    		colander.String(),
		    	title = 'Roommate #2',
			    widget = ChosenSingleWidget(values=names),
    			validator = colander.OneOf(names_validate),
                default = room.name2 or empty,
                missing = None)
            locked = colander.SchemaNode(
			    colander.Bool(),
    			title = 'Locked',
	    		widget = deform.widget.CheckboxWidget(),
                default = room.locked,
                missing = None)
            single = colander.SchemaNode(
                colander.Bool(),
                title = 'Single',
                widget = deform.widget.CheckboxWidget(),
                default = room.single,
                missing = None)

        schema = Schema()
        form = deform.Form(schema, buttons=('submit', 'cancel'))
        if ('submit', u'submit') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
                if appstruct.get('name1', None) == None or appstruct.get('name2', None) == None or appstruct.get('locked', None) == None or appstruct.get('single', None) == None:
                        return HTTPFound(location=request.route_url('view_admin'))
                name1 = appstruct['name1'] if not appstruct['name1'] == empty else None
                name2 = appstruct['name2'] if not appstruct['name2'] == empty else None
                if name1 == name2 and not name1 == None and not name2 == None:
                    request.session.flash('Warning: Names cannot be the same')
                    return HTTPFound(location=request.route_url('view_admin'))

                if name1 and name2 and appstruct['single']: # can't add 2 people to single room
                    request.session.flash('Warning: cannot add two people to a single room')
                    return HTTPFound(location = request.route_url('view_admin'))

                realName1 = realName2 = oldRealName1 = oldRealName2 = None # users' uids for log
                if not name1 == None or not name1 == None:
                    for name in names:
                        if name[0] == name1:
                            realName1 = number_to_username[name[0]]
                        if name[0] == name2:
                            realName2 = number_to_username[name[0]]
                        if name[0] == str(room.name1):
                            oldRealName1 = number_to_username[name[0]]
                        if name[0] == str(room.name2):
                            oldRealName2 = number_to_username[name[0]]

                points = sum(get_points_uidNumbers([name1, name2], request).values())
                if DBSession.query(User).filter(or_( # squatting points
                    and_(User.name == name1, User.number == request.matchdict['room_number']),
                    and_(User.name == name2, User.number == request.matchdict['room_number'])
                    )).first():
                    points += .5

                # removes the new users from other rooms, if they were in a different room
                to_remove = [int(name1 or -1), int(name2 or -1)]
                old_rooms = [room for room in rooms if room.name1 == int(name1 or 0) or room.name1 == int(name2 or 0) or room.name2 == int(name1 or 0) or room.name2 == int(name2 or 0)]
                for room in old_rooms:
                    if room.number == int(request.matchdict['room_number']):
                        continue
                    if room.name1 in to_remove:
                        room.name1 = None
                    if room.name2 in to_remove:
                        room.name2 = None
                    room.points = sum(get_points_uidNumbers([room.name1, room.name2], request).values())

                    DBSession.add(room)

                # update db
                DBSession.query(Room).filter_by(number=
                        request.matchdict['room_number']).update({'name1': name1,
                            'name2': name2, 'locked': appstruct['locked'],
                            'points': points, 'single': appstruct['single']})
                if oldRealName1 != None:
                    send_notification(oldRealName1,
                            "You have been removed from room " + str(room.number) +
                            " by an admin", request)
                if oldRealName2 != None:
                    send_notification(oldRealName2,
                            "You have been removed from room " + str(room.number) +
                            " by an admin", request)
                if realName1 != None:
                    send_notification(realName1, "You have been added to room " +
                            str(room.number) + " by an admin", request)
                if realName2 != None:
                    send_notification(realName2, "You have been added to room " +
                            str(room.number) + " by an admin", request)

                if not oldRealName1 == None and not room.name1 == None:
                    oldNameString1 = oldRealName1 + "(" + str(room.name1) + ")"
                elif not room.name1 == None:
                    oldNameString1 = str(room.name1)
                else:
                    oldNameString1 = "None"
                if not oldRealName2 == None and not room.name2 == None:
                    oldNameString2 = oldRealName2 + "(" + str(room.name2) + ")"
                elif not room.name2 == None:
                    oldNameString2 = str(room.name2)
                else:
                    oldNameString2 = "None"
                if not realName1 == None:
                    realNameString1 = realName1 + "(" + str(name1) + ")"
                elif not name1 == None:
                    realNameString1 = str(name1)
                else:
                    realNameString1 = "None"
                if not realName2 == None:
                    realNameString2 = realName2 + "(" + str(name2) + ")"
                elif not name2 == None:
                    realNameString2 = str(name2)
                else:
                    realNameString2 = "None"
                add_log(uid_number, "edit",
                        str(request.matchdict['room_number']) + " from " +
                        oldNameString1 + ", " + oldNameString2 + " locked: " +
                        str(room.locked) +  " to " +
                        realNameString1 + ", " + realNameString2 + " locked: " +
                        str(appstruct['locked']))
                transaction.commit()
                request.session.flash("Successfully updated room #" +
                        str(request.matchdict['room_number']))
                return HTTPFound(location=request.route_url('view_admin'))
            except deform.ValidationFailure, e:
                return {'locked': site_closed, 'next_room': next_room, 'form': e.render(),
                        'number': request.matchdict['room_number']}
        else: # regular viewing
            return {'locked': site_closed, 'next_room': next_room, 'form': form.render(),
                    'number': request.matchdict['room_number']}

    else: # invalid permissions
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_leave')
def view_leave(request):
    """
    Checks to see if the user is in a room, and if they are, removes the user and
    recalcuates the points for the given room
    """
    global site_closed
    if site_closed:
        return HTTPFound(location = request.route_url('view_main'))

    conn = ldap_conn(request)
    uid = request.headers['X-Webauth-User']
    result = conn.search("uid=" + uid)[0][0][1]
    conn.close()
    uid_number = int(result['uidNumber'][0])
    points = int(result['housingPoints'][0])
    if uid_number == None:
        return HTTPFound(location=request.route_url('view_main'))
    else:
        room = DBSession.query(Room).filter(or_(Room.name1 == uid_number, Room.name2 == uid_number)).first()
        if not room == None:
            if room.locked:
                request.session.flash("Warning: Room is locked, you cannot leave")
                return HTTPFound(location = request.route_url('view_main'))
            if room.name1 == uid_number:
                room.name1 = None
            else:
                room.name2 = None

            # recalculates the points for the given room
            room.points = sum(get_points_uidNumbers([room.name1, room.name2], request).values())
            if not DBSession.query(User).filter(or_(
                and_(User.name == room.name1, User.number == room.number),
                and_(User.name == room.name2, User.number == room.number))).first() == None:
                room.points += .5

            DBSession.add(room)
            add_log(uid_number, "leave", "user left room " + str(room.number))
            request.session.flash("Successfully left room #" + str(room.number))
            transaction.commit()
        else:
            request.session.flash('You are not currently in a room')
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_main', renderer='templates/index.pt')
def view_main(request):
    if 'X-Webaut-User' not in request.headers:
        print 'bad'
    global site_closed, close_time
    session = request.session
    msgs = session.pop_flash()
    conn = ldap_conn(request)
    rooms = DBSession.query(Room).order_by(Room.number).all()
    name_map = dict()
    ids = []
    next_room = None
    uid = request.headers['X-Webauth-User']
    uid_number = get_uid_number(uid, request)
    for room in rooms:
        if room.name1 == uid_number or room.name2 == uid_number:
            next_room = room.number
        if room.name1 is not None:
            ids.append(room.name1)
        if room.name2 is not None:
            ids.append(room.name2)
    if not ids == []:
        for user in conn.search_uid_numbers(ids):
            name_map[int(user[0][1]['uidNumber'][0])] = user[0][1]['cn'][0]
        conn.close()
    current_room = DBSession.query(User).filter_by(name=get_uid_number(uid, request)).first()
    current_room = current_room.number if not current_room == None else None
    admin = isEBoard(uid, request)
    points = get_points_uid(uid, request)
    return {'name_map': name_map, 'rooms': rooms, 'admin': admin, 'points': points,
            'current':  current_room, 'next_room': next_room, 'msgs': msgs,
            'locked': site_closed, 'close_time': close_time}

@view_config(route_name='view_join', renderer='templates/join.pt')
@view_config(route_name='view_join1', renderer='templates/join.pt')
def view_join(request):
    global site_closed
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    number_to_username = {}
    none = 'none'
    names.append((none, '- None -'))
    names_validate.append(none)
    current_room = None # the current room for the user
    current_room_rm = None # the current room for the roommate
    room_id = request.matchdict.get('room_number', "")
    if room_id.isdigit():
        room_id = int(room_id)

    if site_closed:
        return HTTPFound(location=request.route_url('view_main'))

    if ('cancel', u'cancel') in request.POST.items():
        return HTTPFound(location=request.route_url('view_main'))


    active_members = get_active(request)
    uid = request.headers['X-Webauth-User']
    uid_number = get_uid_number(uid, request)
    found_room = False

    # if the user is not in the active members list, they are not allowed to join a room
    for user in active_members:
        if user[1] == uid:
            break
    else:
        request.session.flash('Warning: You are not allowed to signup for a room since you are not an active member with on-floor status')
        return HTTPFound(location = request.route_url('view_main'))

    for room in DBSession.query(Room).order_by(Room.number).all():
        if room_id != "" and room.number == room_id:
            found_room = True
            if room.locked:
                request.session.flash('Warning: Room is locked, you are not allowed to join this room')
                return HTTPFound(location = request.route_url('view_main'))

        if not room.locked:
            numbers_validate.append(room.number)
            numbers.append((room.number, room.number))
        if room.name1 == uid_number: # can't join room if already in one
            current_room = room.number
        if room.name2 == uid_number:
            current_room = room.number
    if room_id != "" and found_room == False:
        request.session.flash('Warning: Room does not exist')
        return HTTPFound(location = request.route_url('view_main'))
    if room_id == "":
        room_id = numbers_validate[0]

    admin = isEBoard(uid, request)
    if not current_room == None:
        request.session.flash('Warning: You are already in a room ' + str(current_room) + '. Leave that room before joining another')
        return HTTPFound(location=request.route_url('view_main'))

    for pair in active_members: # the dats used to validate users to join room
        if not pair[1] == uid:
            names.append((pair[0], pair[2] + " - " + pair[1]))
            names_validate.append(pair[0])
            number_to_username[pair[0]] = pair[1]

    class Schema(colander.Schema):
        roomNumber = colander.SchemaNode(
                colander.Integer(),
                title = 'Room number',
                widget = ChosenSingleWidget(values=numbers),
                validator = colander.OneOf(numbers_validate),
                missing = None,
                default = room_id)
        partnerName = colander.SchemaNode(
                colander.String(),
                title='Roommate\'s name',
                widget=ChosenSingleWidget(values=names),
                validator=colander.OneOf(names_validate),
                missing=None,
                default = none)

    schema = Schema()
    form = deform.Form(schema, buttons=('submit', 'cancel'))

    if  ('submit', u'submit') in request.POST.items():
        try:
            appstruct = form.validate(request.POST.items())
            join_room = DBSession.query(Room).filter_by(number=appstruct['roomNumber']).first()
            if join_room.locked:
                return {'form': 'Room is locked'}
            elif not current_room == None: # do not allow users who are already registered
                request.session.flash('Warning: You are already in room ' + str(current_room) + '. Leave that room before joining another')
                return HTTPFound(location=request.route_url('view_main'))
            elif appstruct['partnerName'].isdigit() and uid_number == int(appstruct['partnerName']):
                request.session.flash('Warning: Why the fuck do you think you could join a room yourself')
                return HTTPFound(location=request.route_url('view_main'))
            elif appstruct.get('partnerName', None) == None or appstruct.get('roomNumber', None) == None:
                return HTTPFound(location=request.route_url('view_main'))
            else:
                points = []
                if not appstruct['partnerName'] == none:
                    points.append(appstruct['partnerName'])
                points.append(uid_number) # the current user's uidNumber
                results = get_points_uidNumbers(points, request)
                test_points = sum(results.values())
                print 'test_points', test_points
                # squatting points
                squating = DBSession.query(User).filter(or_(
                    and_(User.name == (appstruct['partnerName'] if appstruct['partnerName'] != none else None),
                        User.number == appstruct['roomNumber']),
                    and_(User.name == uid_number, User.number == appstruct['roomNumber']))).first()
                if squating:
                    test_points += .5

                if join_room.single and appstruct['partnerName'] != none: # room is single and trying to join with roommate
                    request.session.flash("Warning: Cannot join the single with a roommate")
                    return HTTPFound(location=request.route_url('view_main'))

                partner = int(appstruct['partnerName'] if appstruct['partnerName'] != none else -1)
                p_room = DBSession.query(Room).filter(or_(Room.name1 == partner, Room.name2 == partner)).first()
                p_user = DBSession.query(User).filter_by(name = partner).first()
                print 'test: ', p_user
                if not p_user or p_user.roommate != uid_number:
                    request.session.flash('Warning: You are not allowed to control this person\'s housing status')
                    return HTTPFound(location=request.route_url('view_main'))

                # roommate is already in another room
                if p_room and p_room.number != int(appstruct['roomNumber']):

                    # if the user does not have permission to pull the roommate out of their current room
                    if p_user and p_user.roommate != uid_number and p_user.roommate != None:
                        request.session.flash('Warning: Roomate is already in another room')
                        return HTTPFound(location=request.route_url('view_main'))

                    # else the user has permission to pull the user out of their current room
                    elif p_user:
                        new_points = sum(get_points_uidNumbers([room.name1, room.name2], request).values())
                        if p_room.name1 == partner:
                            DBSession.query(Room).filter_by(name1 = partner).update({'name1': None, 'points': new_points})
                        else:
                            DBSession.query(Room).filter_by(name2 = partner).update({'name2': None, 'points': new_points})
                    else:
                        request.session.flash('Warning: Roomate is already in another room')
                        return HTTPFound(location=request.route_url('view_main'))

                else:
                    # if the current user is allowed to change the other user's room status
                    if p_user and p_user.roommate != uid_number and p_user.roommate != None:
                        request.session.flash("Warning: The roommate you tried " +
                                "to join with does not allow you to control their housing status. Please tell them to select you as a roommate")
                        return HTTPFound(location=request.route_url('view_main'))

                # only one person in room and joining alone
                if (join_room.name1 == None or join_room.name2 == None) and appstruct['partnerName'] == none and not join_room.single:

                    if join_room.name1 == None:
                        join_room.name1 = uid_number
                    else:
                        join_room.name2 = uid_number
                    join_room.points += results[uid_number]
                    if squating and join_room.points == int(join_room.points):
                        join_room.points += .5
                    DBSession.add(join_room)
                    send_notification(uid, "You have joined room " + str(appstruct['roomNumber']), request)
                    add_log(uid_number, "join", "room " + str(appstruct['roomNumber']))
                elif join_room.points < test_points: # if new people beat out current ocupents
                    if appstruct['partnerName'] == none: # user joined alone and kicked current members
                        # old residents were kicked
                        if not join_room.name1 == None or not join_room.name2 == None:
                            users = str(join_room.name1) if not join_room.name1 == None else ""
                            if users == "":
                                users = str(join_room.name2)
                            else:
                                users += " & " + str(join_room.name2)
                            add_log(uid_number, "join", "user joined room " + str(appstruct['roomNumber']) + ", kicking " + users)
                            uid1 = None
                            uid2 = None
                            for name in names:
                                if names[0] == str(room.name1):
                                    uid1 = number_to_username[name[0]] #names[1][names[1].index('-') + 1:]
                                elif names[0] == str(room.name2):
                                    uid2 = number_to_username[name[0]] #names[1][names[1].index('-') + 1:]
                                if uid != None and uid != None:
                                    break
                            if uid1 != None:
                                send_notification(uid1, "You have been kicked from room " + str(appstruct['roomNumber']), request)
                            if uid2 != None:
                                send_notification(uid2, "You have been kicked from room " + str(appstruct['roomNumber']), request)
                        else:
                           add_log(uid_number, "join", "user joined room alone")
                    else: # user joined with a roommate
                        if not join_room.name1 == None or not join_room.name2 == None:
                            partnerString = kickString1 = kickString2 = None
                            users = str(join_room.name1) if not join_room.name1 == None else ""
                            if users == "":
                                users = str(join_room.name2)
                            else:
                                users += " & " + str(join_room.name2)
                            for name in names:
                                if name[0] == str(appstruct['partnerName']):
                                    partnerString = number_to_username[name[0]] #name[1][name[1].index('-') + 1:].strip()
                                if name[0] == str(join_room.name1):
                                    kickString1 = number_to_username[name[0]] #name[1][name[1].index('-') + 1:].strip()
                                if name[0] == str(join_room.name2):
                                    kickString2 = number_to_username[name[0]] #name[1][name[1].index('-') + 1:].strip()

                            if partnerString and kickString1:
                                send_notification(kickString1, "You have been kicked from room " + str(appstruct['roomNumber']) +
                                    " by " + uid + " and " + partnerString, request)
                            if partnerString and kickString2:
                                send_notification(kickString2, "You have been kicked from room " + str(appstruct['roomNumber']) +
                                    " by " + uid + " and " + partnerString, request)


                            send_notification(partnerString, "You have joined room " + str(appstruct['roomNumber']) + " with " + uid, request)

                            if not kickString1 == None and not join_room.name1 == None:
                                kickString = kickString1 + "(" + str(join_room.name1) + ")"
                            elif not join_room.name1 == None:
                                kickString = str(join_room.name1)
                            else:
                                kickString = ""

                            if kickString == "":
                                if not kickString2 == None and not join_room.name2 == None:
                                    kickString = kickString2 + "(" + str(join_room.name2) + ")"
                                elif not join_room.name2 == None:
                                    kickString = str(join_room.name2)
                            else:
                                if not kickString2 == None and not join_room.name2 == None:
                                    kickString += " & " + kickString2 + "(" + str(join_room.name2) + ")"
                                elif not join_room.name2 == None:
                                    kickString += " & " + str(join_room.name2)

                            if not partnerString == None:
                                partnerString = partnerString + "(" + str(appstruct['partnerName']) + ")"
                            else:
                                partnerString = appstruct['partnerName']
                            add_log(uid_number, "join",
                                "room " + str(appstruct['roomNumber']) + " with " +
                                partnerString + ", kicking " + kickString)
                        else: # joined with partner and did not kick anyone
                            print 'fdsjahjkfldskhfjkds'
                            for name in names:
                                if name[0] == str(appstruct['partnerName']):
                                    partner = int(appstruct['partnerName'])
                                    room = DBSession.query(Room).filter(or_(Room.name1 == partner, Room.name2 == partner)).first()
                                    if room: # updates the points for the roommate's old room
                                        if room.name1 == partner:
                                            room.name1 = None
                                        else:
                                            room.name2 = None
                                        #room.points = sum(get_points_uidNumbers([room.name1, room.name2], request).values())

                                    send_notification(number_to_username[name[0]],
                                            "Joined room " + str(appstruct['roomNumber']) + " with " + uid, request)
                                    add_log(uid_number, "join", "room " + str(appstruct['roomNumber']) + " with " +
                                            name[1] + "(" + str(appstruct['partnerName']) + ")")
                                    break
                            else:
                                DBSession.add(Log(uid_number, "join", "room " + str(appstruct['roomNumber']) + " with " +
                                    str(appstruct['partnerName'])))

                    DBSession.query(Room).filter_by(number=appstruct['roomNumber']).update(
                            {"name2": int(appstruct['partnerName'])
                                if not appstruct['partnerName'] == none else None,
                                "name1": uid_number, "points": test_points})
                    transaction.commit()
                else:
                    request.session.flash('Warning: You do not have enough housing points')
                    return HTTPFound(location=request.route_url('view_main'))
            request.session.flash('Successfully joined room ' + str(appstruct['roomNumber']))
            return HTTPFound(location=request.route_url('view_main'))
        except deform.ValidationFailure, e:
            return {'form': e.render(), 'admin': admin}
    else:
        return {'form': form.render(), 'admin': admin}
