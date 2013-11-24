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
        roommates = roommatePair.prepare_roommates_for_html(request)

        # forms for the admin panel
        roommate_form = deform.Form(NewRoommate(names, names_validate), buttons=('submit',))
        form = deform.Form(NewRoomsSchema(room_numbers), buttons=('submit',))
        form['new_rooms'].widget = deform.widget.SequenceWidget(min_len=1)
        current_rooms_schema = Current_Rooms_Schema(names, names_validate, numbers, numbers_validate)
        current_rooms_form = deform.Form(current_rooms_schema, buttons=('submit',))
        time_set = deform.Form(TimeSchema(site_closed, open_time, close_time), buttons=('submit',))

        if request.method == 'POST':
            # delete current room assignments
            if request.POST.get('remove_roommate'):
                if roommatePair.remove_pair(int(request.POST.get('remove_roommate'))):
                    request.session.flash('Successfully removed user\'s roommate')
                else:
                    request.session.flash('Failed to remove roommate pair')
            # current room was given
            elif request.POST.get('__start__') == u'current_rooms:sequence':
                try:
                    appstruct = current_rooms_form.validate(request.POST.items())
                    for current_room in appstruct['current_rooms']: # new current rooms
                        user.create_current_room(int(current_room['uid_number']), int(current['room_number']))
                    request.session.flash('Successfully added current room(s)')
                except deform.ValidationFailure, e:
                    request.session.flash('Warning: Could not add current room assignment')
                    current_rooms_form = e
            # settings were given
            elif request.POST.get('__start__') == u'close_time:mapping':
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
                'time': time_set.render(), 'roommate_renderer': roommate_form.render(),
                'roommates': roommates}
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

    none = 'none'

    if site_closed:
        return HTTPFound(location=request.route_url('view_main'))

    if request.POST.get('cancel'):
        return HTTPFound(location=request.route_url('view_main'))

    uid = request.headers['X-Webauth-User']

    if not user.is_active(uid):
        request.session.flash('Warning: You are not allowed to signup for a room since you are not an active member with on-floor status')
        return HTTPFound(location = request.route_url('view_main'))

    uid_number = ldap_conn.get_uid_number(uid, request)
    room_numbers, numbers_validate = room.get_valid_rooms()
    names, names_validate = user.get_valid_roommates(request.headers['X-Webauth-User'])
    names.append((None, '- None -'))
    names_validate.append(none)
    admin = user.is_admin(uid)

    form = deform.Form(JoinSchema(room_numbers, numbers_validate, names, names_validate),
            buttons=('submit', 'cancel'))

    if request.POST.get('submit'):
        try:
            appstruct = form.validate(request.POST.items())
            if room.signup_for_room(int(appstruct['room_number']), uid_number, int(appstuct['roommate']), request):
                request.session.flash('Successfully joined room')
            else:
                return {'form': 'Failed to join room'}
        except deform.ValidationFailure, e:
            return {'form': e.render(), 'admin': admin}
    else:
        return {'form': form.render(), 'admin': admin}
