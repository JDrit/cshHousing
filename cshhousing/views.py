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
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer
from translationstring import TranslationStringFactory
from ldap_conn import *
from datetime import datetime
from threading import Timer
import subprocess
import requests
import user
import log
import ldap_conn
from schemas import *

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

def translator(term):
    return get_localizer(get_current_request()).translate(term)
    deform_template_dir = resource_filename('deform', 'templates/')
    zpt_renderer = deform.ZPTRendererFactory(
                [deform_template_dir], translator=translator)

@view_config(context=HTTPNotFound, renderer='templates/404.pt')
def view_404(request):
    global site_closed
    admin = user.is_admin(request.headers['X-Webauth-User'])
    uid_number = ldap_conn.get_uid_number(request.headers['X-Webauth-User'], request)
    room = room.get_users_room(uid_number)
    return {'admin': admin, 'locked': site_closed, 'next_room': room}

@view_config(route_name='view_settings', renderer='templates/settings.pt')
def view_settings(request):
    global site_closed
    msg = None
    uid_number = ldap_conn.get_uid_number(request.headers['X-Webauth-User'], request)
    next_room = room.get_users_room(uid_number)
    admin = user.is_admin(request.headers['X-Webauth-User'])
    none = 'none'

    names, names_validate = user.get_valid_roommates(request.headers['X-Webauth-User'])
    names.append((none, '- None -')) # adds the info for choosing no roommate
    names_validate.append(none)

    form = deform.Form(SettingsSchema(uid_number, names, names_validate), buttons = ('submit', 'cancel'))

    if ('submit', u'submit') in request.POST.items():
        try:
            appstruct = form.validate(request.POST.items())
            if appstruct['roommate'] != none:
                roommate_id = int(appstruct['roommate'])
            else:
                roommate_id = None
            user.update_user_info(uid_number, send_email = appstruct['send_email'],
                    roommate_id = roommate_id)

            msg = 'Your user settings have been updated'

            form = deform.Form(SettingsSchema(uid_number, names, names_validate), buttons = ('submit', 'cancel'))
        except deform.ValidationFailure, e:
            form = e

    return {'admin': admin, 'form': form.render(), 'msg': msg,
            'locked': site_closed, 'next_room': next_room}

@view_config(route_name='view_delete_logs')
def view_delete_logs(request):
    if user.is_admin(request.headers['X-Webauth-User']):
        log.clear_logs(ldap_conn.get_uid_number(request.headers['X-Webauth-User']))
        request.session.flash("Logs cleared")
        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_delete_current')
def view_delete_current(request):
    """
    This is called when an admin decides to delete a current room assignment
    """
    if user.is_admin(request.headers['X-Webauth-User']):
        try:
            uid_number = int(request.matchdict['name'])
            user.remove_current_room(uid_number)
            request.session.flash("Successfully deleted current room assignment")
        except NoResultFound, e:
            request.session.flash("Warning: could not delete current room assignment")
        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_admin', renderer='templates/admin.pt')
def view_admin(request):
    global site_closed, close_time, lock_thread, open_thread, open_time

    if user.is_admin(request.headers['X-Webauth-User']):
        uid_number = ldap_conn.get_uid_number(request.headers['X-Webauth-User'], request)

        # gets the info for valid rooms and users
        room_numbers, numbers_validate = room.get_valid_rooms()
        names, names_validate = user.get_valid_roommates(request.headers['X-Webauth-User'])
        logs = log.get_logs()
        rooms = prepare_rooms_for_html(request)
        next_room = room.get_users_room(user.get_users(uid_number(uid_number)))

        # forms for the admin panel
        roommate_form = deform.Form(NewRoommate(names, names_validate), buttons=('submit',))
        form = deform.Form(NewRoomsSchema(room_numbers), buttons=('submit',))
        form['new_rooms'].widget = deform.widget.SequenceWidget(min_len=1)
        current_rooms_schema = Current_Rooms_Schema(names, names_validate, numbers, numbers_validate)
        current_rooms_form = deform.Form(current_rooms_schema, buttons=('submit',))
        time_set = deform.Form(TimeSchema(site_closed, open_time, close_time), buttons=('submit',))

        if request.method == 'POST':
            # delete current room assignments
            if 'remove_roommate' in [item[0] for item in request.POST.items()]:
                if roommatePair.remove_pair(int(request.POST.get('roommate_id'))):
                    request.session.flash('Successfully removed user\'s roommate')
                else:
                    request.session.flash('Failed to remove roommate pair')
            # current room was given
            elif ('__start__', u'current_rooms:sequence') in request.POST.items():
                try:
                    appstruct = current_rooms_form.validate(request.POST.items())
                    for current_room in appstruct['current_rooms']: # new current rooms
                        user.create_current_room(int(current_room['uid_number']), int(current['room_number']))
                    request.session.flash('Successfully added current room(s)')
                except deform.ValidationFailure, e:
                    request.session.flash('Warning: Could not add current room assignment')
                    current_rooms_form = e
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
                        log.add_log(uid_number, "lock", "site will close at "  + str(close_time))
                        request.session.flash("Site will close at " + str(close_time))
                    if open_time != None:
                        open_thread = Timer((open_time.replace(tzinfo=None) -
                            datetime.now()).seconds, unlock_site)
                        open_thread.start()
                        log.add_log(uid_number, "lock", "site will now open at " + str(open_time))
                        request.session.flash("Site will open at " + str(open_time))
                    if site_closed:
                        log.add_log(uid_number, "lock", "site was closed")
                        request.session.flash("Site is now closed")
                    else:
                        log.add_log(uid_number, "lock", "site was opened")
                        request.session.flash("Site is now open")
                except deform.ValidationFailure, e:
                    request.session.flash('Warning: Could not parse time inputs')
                except Time_Exception, e:
                    request.session.flash("Warning: " + str(e))
            else: # adds a new roommate pair
                try:
                    appstruct = roommate_form.validate(request.POST.items())
                    roommatePair.add_roommate_pair(int(appstruct['uid_number1']), int(appstruct['uid_number2']))
                    request.session.flash('Successfully updaed roommate pairs')
                except deform.ValidationFailure, e:
                    request.session.flash('Warning: Could not parse input')
                    roommate_form = e

        return {'rooms': rooms, 'form': form.render(), 'users': users,
                'current_rooms_form': current_rooms_form.render(),
                'msgs': request.session.pop_flash(), 'locked': site_closed, 'next_room': next_room, 'logs': logs,
                'time': time_set.render(), 'roommate_renderer': roommate_form.render()}
    else:
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_admin_edit', renderer='templates/edit.pt')
def view_admin_edit(request):
    global site_closed
    room_number = int(request.matchdict['room_number'])
    uid_number = ldap_conn.get_uid_number(request.headers['X-Webauth-User'], request)
    next_room = user.get_users_room(uid_number)
    names, names_validate = user.get_valid_roommates(request.headers['X-Webauth-User'])
    empty = 'empty'
    names.append((empty, '- Empty -'))
    names_validate.append(empty)
    form = deform.FormAdmin(AdminRoomEdit(names, names_validate), buttons=('submit', 'cancel'))

    if user.is_admin(request.headers['X-Webauth-User']):
        if ('cancel', u'cancel') in request.POST.items():
            return HTTPFound(location=request.route_url('view_admin'))
        elif ('submit', u'submit') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
                uid_number1 = appstruct.get('uid_number1') if not appstruct.get('uid_number1') == empty else None
                uid_number2 = appstruct.get('uid_number2') if not appstruct.get('uid_number2') == empty else None

                if user.admin_update_room(room_number, uid_number1, uid_number2, appstruct.get('locked'), appstruct.get('single'), request):
                    request.session.flash("Successfully updated room #" + str(room_number))
                else:
                    request.session.flash("Failed to update room #" + str(room_number))
                return HTTPFound(location=request.route_url('view_admin'))
            except deform.ValidationFailure, e:
                return {'locked': site_closed, 'next_room': next_room, 'form': e.render(), 'number': room_number}
        else: # regular viewing
            return {'locked': site_closed, 'next_room': next_room, 'form': form.render(), 'number': room_number}
    else: # invalid permissions
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_leave')
def view_leave(request):
    global site_closed

    if site_closed:
        return HTTPFound(location = request.route_url('view_main'))

    uid = request.headers['X-Webauth-User']
    uid_number = ldap_conn.get_uid_number(uid)
    points = user.get_points(uid_number)
    room = room.get_users_room(uid_number)

    if room: # user is in a room
        if room.locked:
            request.session.flash("Warning: Room is locked, you cannot leave")
            return HTTPFound(location = request.route_url('view_main'))
        room.leave_room(uid_number)
        request.session.flash("Successfully left room #" + str(room.number))
    else:
        request.session.flash('You are not currently in a room')
    return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_main', renderer='templates/index.pt')
def view_main(request):
    global site_closed, close_time

    uid = request.headers['X-Webauth-User']
    uid_number = get_uid_number(uid, request)
    rooms = room.prepare_rooms_for_html()
    next_room = room.get_users_room(uid_number)
    current_room = user.get_current_room(uid_number)
    admin = user.is_admin(uid)
    points = user.get_points(request, uid_number)

    return {'rooms': rooms, 'admin': admin, 'points': points,
            'current':  current_room, 'next_room': next_room,
            'msgs': request.session.pop_flash(),
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
