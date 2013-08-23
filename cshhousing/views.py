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
from .models import DBSession, Room, User, Log
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer
from translationstring import TranslationStringFactory
from ldap_conn import ldap_conn
from datetime import datetime
from threading import Timer

_ = TranslationStringFactory('deform')
css = HtmlFormatter().get_style_defs('.highlight')

siteClosed = False # boolean used to determine if users can modify the layout
closeTime = None   # the time to auto close the site
lock_thread = None # this is the thread that will lock the site at a given time

def lock_site():
    """
    This is the function that is run as a delay to lock the site at a given time
    """
    global siteClosed
    siteClosed = True

def translator(term):
    return get_localizer(get_current_request()).translate(term)
    deform_template_dir = resource_filename('deform', 'templates/')
    zpt_renderer = deform.ZPTRendererFactory(
                [deform_template_dir], translator=translator)

@view_config(route_name='view_settings', renderer='templates/settings.pt')
def view_settings(request):
    msg = None
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])
    admin = conn.isEBoard(request.headers['X-Webauth-User'])
    conn.close()
    query = DBSession.query(User).filter_by(name = 10387).first()
    print query
    status = False if not query else query.send
    class Schema(colander.Schema):
        send_email = colander.SchemaNode(
                colander.Bool(),
                title = 'Send Email',
                description = 'This will send emails to your CSH account when changes occur to your housing status',
	    		widget = deform.widget.CheckboxWidget(),
                default = status)

    form = deform.Form(Schema(), buttons=('submit', 'cancel'))
    form_render = form.render()
    if ('submit', u'submit') in request.POST.items():
        try:
            appstruct = form.validate(request.POST.items())
            if not query:
                DBSession.add(User(10387, send = appstruct['send_email']))
            else:
                DBSession.query(User).filter_by(name = 10387).update({'send': appstruct['send_email']})
            status = appstruct['send_email']
            if status:
                msg = 'Emails will now be sent to you when your housing status changes'
            else:
                msg = 'Emails will now NOT be sent to you anymore'

            # class is defined again to allow for the default to be changed to the new setting
            class Schema(colander.Schema):
                send_email = colander.SchemaNode(
                        colander.Bool(),
                        title = 'Send Email',
                        description = 'This will send emails to your CSH account when changes occur to your housing status',
        	    		widget = deform.widget.CheckboxWidget(),
                        default = status)

            form_render = deform.Form(Schema(), buttons=('submit', 'cancel')).render()
            transaction.commit()
        except deform.ValidationFailure, e:
            form_render = e.render()

    return {'admin': admin, 'form': form_render, 'msg': msg}

@view_config(context=HTTPNotFound, renderer='templates/404.pt')
def view_404(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])
    admin = conn.isEBoard(request.headers['X-Webauth-User'])
    conn.close()
    return {'admin': admin}

@view_config(route_name='view_delete_logs')
def view_delete_logs(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'],
            settings['password'], settings['base_dn'])
    if conn.isEBoard(request.headers['X-Webauth-User']):
        DBSession.query(Log).delete()
        transaction.commit()
        conn.close()
        request.session.flash("Logs cleared")
        return HTTPFound(request.route_url('view_admin'))
    else:
        conn.close()
        return HTTPFound(request.route_url('view_main'))


@view_config(route_name='view_delete')
def view_delete(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'],
            settings['password'], settings['base_dn'])

    if conn.isEBoard(request.headers['X-Webauth-User']):
        try:
            DBSession.delete(DBSession.query(Room).filter_by(
                number = request.matchdict['room_number']).one())
            request.session.flash("Successfully deleted room #" +
                    str(request.matchdict['room_number']))
            DBSession.add(Log(10387, "delete", "room " + str(request.matchdict['room_number']) +
                "  was deleted"))
            transaction.commit()
        except NoResultFound, e:
            request.session.flash("Warning: Could not delete room")

        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_delete_current')
def view_delete_current(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard(request.headers['X-Webauth-User']):
        try:
            DBSession.delete(DBSession.query(User).filter_by(name = request.matchdict['name']).one())
            room = DBSession.query(Room).filter(or_(Room.name1 == int(request.matchdict['name']), Room.name2 == int(request.matchdict['name']))).first()
            if room != None:
                room.points = sum(conn.get_points_uidNumbers([room.name1, room.name2]).values())
                if not DBSession.query(User).filter(or_( # squatting points
                    and_(User.name == room.name1, User.number == room.number),
                    and_(User.name == room.name2, User.number == room.number)
                    )).first() == None:
                    room.points += .5
                DBSession.add(room)
            request.session.flash("Successfully deleated current room assignment")
            result = conn.search("uidNumber=" + request.matchdict['name'])
            uid = result[0][0][1]['uid'][0] + "(" + str(request.matchdict['name']) + ")" if result != [] else str(request.matchdict['name'])
            DBSession.add(Log(10387, "delete current", uid + "'s current room was deleted"))
            transaction.commit()
        except NoResultFound, e:
            request.session.flash("Warning: could not delete current room assignment")
        conn.close()
        return HTTPFound(request.route_url('view_admin'))
    else:
        conn.close()
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_admin', renderer='templates/admin.pt')
def view_admin(request):
    global siteClosed, closeTime, lock_thread
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard(request.headers['X-Webauth-User']):
        rooms = DBSession.query(Room).all()
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

        for element in conn.get_active():
            names.append((element[0][1]['uidNumber'][0], element[0][1]['uid'][0]))
            names_validate.append(element[0][1]['uidNumber'][0])


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
                    default = siteClosed,
                    description = "Locks the site so no users can change their status")
            date_time = colander.SchemaNode(
                    colander.DateTime(),
                    widget = DateTimeInputWidget(),
                    missing = None,
                    default = closeTime,
                    description = "Give a time if you want the site to auto lock at a given time")

        schema = New_Rooms_Schema()
        form = deform.Form(schema, buttons=('submit',))
        form['new_rooms'].widget = deform.widget.SequenceWidget(min_len=1)
        form_render = form.render()
        current_rooms_schema = Current_Rooms_Schema()
        current_rooms_form = deform.Form(current_rooms_schema, buttons=('submit',))
        current_rooms_form_render = current_rooms_form.render()
        time_set = deform.Form(Time_Schema(), buttons=('submit',))
        msgs = request.session.pop_flash()
        # new room was given
        if ('__start__', u'new_rooms:sequence') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
                rooms_added = 0
                for new_room in appstruct['new_rooms']:
                    if not new_room['number'] in room_numbers:
                        room = Room(new_room['number'], new_room['locked'], new_room['single'])
                        DBSession.add(room)
                        room_numbers.add(new_room['number'])
                        rooms_added += 1
                        DBSession.add(Log(10387, "new room added",
                            "added room #" + str(new_room['number'])))
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
                    if DBSession.query(User).filter_by(name =current_room['name']).update({'number': current_room['number']}) == 0:
                        user = User(current_room['name'], current_room['number'])
                        DBSession.add(user)
                        rooms_added += 1
                        DBSession.add(Log(10387, "current room added",
                            "added room #" + str(current_room['number'])))

                    room = DBSession.query(Room).filter(or_(Room.name1 == current_room['name'], Room.name2 == current_room['name'])).first()
                    if room != None:
                        room.points = sum(conn.get_points_uidNumbers([room.name1, room.name2]).values())
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
        elif ('__start__', u'date_time:mapping') in request.POST.items():
            try:
                appstruct = time_set.validate(request.POST.items())
                siteClosed = bool(appstruct['lock'])
                closeTime = appstruct['date_time']
                if lock_thread != None:
                    lock_thread.cancel()
                if closeTime != None:
                    lock_thread = Timer((closeTime.replace(tzinfo=None) - datetime.now()).seconds, lock_site)
                    lock_thread.start()
                    if not siteClosed:
                        msgs.append("Site is OPEN and will close at " + str(closeTime.strftime('%b %d, %Y %I:%M:00 %p')))
                        DBSession.add(Log(10387, "lock", "site was opened"))
                    else:
                        msgs.append("Site is now CLOSED")
                        DBSession.add(Log(10387, "lock", "site was closed"))
                else:
                    if siteClosed:
                        msgs.append("Site is now CLOSED")
                        DBSession.add(Log(10387, "lock", "site was closed"))
                    else:
                        msgs.append("Site is now OPEN")
                        DBSession.add(Log(10387, "lock", "site was opened"))
            except deform.ValidationFailure, e:
                msgs.append('Warning: Could not parse time inputs')
        logs = DBSession.query(Log).limit(100).all()
        logs.reverse()
        users = DBSession.query(User).all()
        for user in users:
            ids.add(user.name)
        for log in logs:
            ids.add(log.uid_number)
        if not ids == set():
            for user in conn.search_uids(list(ids)):
                name_map[int(user[0][1]['uidNumber'][0])] = user[0][1]['uid'][0]
                points_map[int(user[0][1]['uidNumber'][0])] = 5 #user[0][1]['housingPoints'][0]

        conn.close()
        return {'name_map': name_map, 'rooms': rooms, 'form': form_render, 'users': users,
                'points_map': points_map, 'current_rooms_form': current_rooms_form_render,
                'msgs': msgs, 'locked': siteClosed, 'logs': logs, 'time': time_set.render()}
    else:
        conn.close()
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_admin_edit', renderer='templates/edit.pt')
def view_admin_edit(request):
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    empty = 'empty'
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard(request.headers['X-Webauth-User']):

        if ('cancel', u'cancel') in request.POST.items():
            return HTTPFound(location=request.route_url('view_admin'))
        rooms = DBSession.query(Room).all()
        for r in rooms:
            if str(r.number) == request.matchdict['room_number']:
                room = r
                break
        else:
            request.session.flash("Warning: Invalid room number")
            return HTTPFound(location=request.route_url('view_admin'))

        names.append((empty, '- Empty -'))
        names_validate.append(empty)
        for element in conn.get_active():
            names.append((element[0][1]['uidNumber'][0], element[0][1]['uid'][0]))
            names_validate.append(element[0][1]['uidNumber'][0])
        class Schema(colander.Schema):
            name1 = colander.SchemaNode(
		    	colander.String(),
			    title = 'Roommate #1',
    			widget = ChosenSingleWidget(values=names),
	    		validator = colander.OneOf(names_validate),
                default = room.name1 or empty)
            name2 = colander.SchemaNode(
	    		colander.String(),
		    	title = 'Roommate #2',
			    widget = ChosenSingleWidget(values=names),
    			validator = colander.OneOf(names_validate),
                default = room.name2 or empty)
            locked = colander.SchemaNode(
			    colander.Bool(),
    			title = 'Locked',
	    		widget = deform.widget.CheckboxWidget(),
                default = room.locked)
            single = colander.SchemaNode(
                colander.Bool(),
                title = 'Single',
                widget = deform.widget.CheckboxWidget(),
                default = room.single)

        schema = Schema()
        form = deform.Form(schema, buttons=('submit', 'cancel'))

        if ('submit', u'submit') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
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
                           realName1 = name[1]
                        if name[0] == name2:
                            realName2 = name[1]
                        if name[0] == str(room.name1):
                            oldRealName1 = name[1]
                        if name[0] == str(room.name2):
                            oldRealName2 = name[1]

                points = sum(conn.get_points_uidNumbers([name1, name2]).values())
                if not DBSession.query(User).filter(or_( # squatting points
                    and_(User.name == name1, User.number == request.matchdict['room_number']),
                    and_(User.name == name2, User.number == request.matchdict['room_number'])
                    )).first() == None:
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
                    room.points = sum(conn.get_points_uidNumbers([room.name1, room.name2]).values())
                    DBSession.add(room)

                # update db
                DBSession.query(Room).filter_by(number=
                        request.matchdict['room_number']).update({'name1': name1,
                            'name2': name2, 'locked': appstruct['locked'], 'points': points, 'single': appstruct['single']})

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

                DBSession.add(Log(10387, "edit", str(request.matchdict['room_number']) + " from " +
                    oldNameString1 + ", " + oldNameString2 + " locked: " + str(room.locked) +  " to " +
                    realNameString1 + ", " + realNameString2 + " locked: " + str(appstruct['locked'])))
                transaction.commit()
                conn.close()
                request.session.flash("Successfully updated room #" + str(request.matchdict['room_number']))
                return HTTPFound(location=request.route_url('view_admin'))
            except deform.ValidationFailure, e:
                conn.close()
                return {'form': e.render(), 'number': request.matchdict['room_number']}
        else: # regular viewing
            conn.close()
            return {'form': form.render(), 'number': request.matchdict['room_number']}

    else: # invalid permissions
        conn.close()
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_leave')
def view_leave(request):
    """
    Checks to see if the user is in a room, and if they are, removes the user and
    recalcuates the points for the given room
    """
    global siteClosed
    if siteClosed:
        return HTTPFound(location = request.route_url('view_main'))

    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])
    result = conn.search("uid=jd")[0][0][1]
    uid_number = int(result['uidNumber'][0])
    points = 2 #int(result['housingPoints'][0])
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
            room.points = sum(conn.get_points_uidNumbers([room.name1, room.name2]).values())
            if not DBSession.query(User).filter(or_(
                and_(User.name == room.name1, User.number == room.number),
                and_(User.name == room.name2, User.number == room.number))).first() == None:
                room.points += .5

            DBSession.add(room)
            DBSession.add(Log(10387, "leave", "user left room " + str(room.number)))
            request.session.flash("Successfully left room #" + str(room.number))
            transaction.commit()
        else:
            request.session.flash('You are not currently in a room')
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_main', renderer='templates/index.pt')
def view_main(request):

    global siteClosed, closeTime
    session = request.session
    msgs = session.pop_flash()
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])
    rooms = DBSession.query(Room).all()
    name_map = dict()
    ids = []
    next_room = None
    uid = request.headers['X-Webauth-User']
    uid_number = conn.get_uid_number(uid)
    for room in rooms:
        if room.name1 == uid_number or room.name2 == uid_number:
            next_room = room.number
        if room.name1 is not None:
            ids.append(room.name1)
        if room.name2 is not None:
            ids.append(room.name2)
    if not ids == []:
        for user in conn.search_uids(ids):
            name_map[int(user[0][1]['uidNumber'][0])] = user[0][1]['uid'][0]
    current_room = DBSession.query(User).filter_by(name=conn.get_uid_number(uid)).first()
    current_room = current_room.number if not current_room == None else None
    return {'name_map': name_map, 'rooms': rooms, 'admin': True, 'points': conn.get_points_uid(uid),
            'current':  current_room, 'next_room': next_room, 'msgs': msgs,
            'locked': siteClosed, 'closeTime': closeTime}

@view_config(route_name='view_join', renderer='templates/join.pt')
def view_join(request):
    global siteClosed
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    none = 'none'
    names.append((none, '- None -'))
    names_validate.append(none)
    current_room = None # the current room for the user
    current_room_rm = None # the current room for the roommate

    uid = request.headers['X-Webauth-User']
    if siteClosed:
        return HTTPFound(location=request.route_url('view_main'))

    if ('cancel', u'cancel') in request.POST.items():
        return HTTPFound(location=request.route_url('view_main'))

    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    uidNumber = conn.get_uid_number(uid)
    admin = conn.isEBoard(uid)
    for room in DBSession.query(Room).all():
        if not room.locked:
            numbers_validate.append(room.number)
            numbers.append((room.number, room.number))
        if room.name1 == uidNumber: # can't join room if already in one
            current_room = room.name1
        if room.name2 == uidNumber:
            current_room = room.name2

    if not current_room == None:
        request.session.flash('Warning: You are already in room ' + str(current_room) + '. Leave that room before joining another')
        return HTTPFound(location=request.route_url('view_main'))


    for element in conn.get_active():
        if not element[0][1]['uid'][0] == uid:
            names.append((element[0][1]['uidNumber'][0], element[0][1]['uid'][0]))
            names_validate.append(element[0][1]['uidNumber'][0])

    class Schema(colander.Schema):
        roomNumber = colander.SchemaNode(
                colander.Integer(),
                title='Room number',
                widget=ChosenSingleWidget(values=numbers),
                validator= colander.OneOf(numbers_validate),
                missing=colander.required)
        partnerName = colander.SchemaNode(
                colander.String(),
                title='Roommate\' name',
                widget=ChosenSingleWidget(values=names),
                validator=colander.OneOf(names_validate),
                missing=colander.required,
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
            else:
                test_points = 0 # the amount of points for the people trying to join
                points = []
                if not appstruct['partnerName'] == none:
                    points.append(appstruct['partnerName'])
                points.append(10387) # the current user's uidNumber
                results = conn.get_points_uidNumbers(points)

                test_points += results.get(appstruct['partnerName'], 0)
                test_points += results[10387]
                # squatting points
                squating = DBSession.query(User).filter(or_(
                    and_(User.name == appstruct['partnerName'], User.number == appstruct['roomNumber']),
                    and_(User.name == 10387, User.number == appstruct['roomNumber']))).first()
                if squating:
                    test_points += .5
                if join_room.single and appstruct['partnerName'] != none: # room is single and trying to join with roommate
                    request.session.flash("Warning: Cannot join the single with a roommate")
                    return HTTPFound(location=request.route_url('view_main'))
                if DBSession.query(Room).filter(or_(Room.name1 == int(appstruct['partnerName'] if appstruct['partnerName'] != none else -1),
                    Room.name2 == int(appstruct['partnerName'] if appstruct['partnerName'] != none else -1))).first() != None:
                    request.session.flash("Warning: Roommate is already in another room, they need to leave before you can join a room with them")
                    return HTTPFound(location=request.route_url('view_main'))
                if (join_room.name1 == None or join_room.name2 == None) and appstruct['partnerName'] == none and not join_room.single: # only one person in room and joining alone
                    if join_room.name1 == None:
                        join_room.name1 = 10387
                    else:
                        join_room.name2 = 10387
                    join_room.points += results[10387]
                    if squating:
                        join_room.points += .5
                    DBSession.add(join_room)
                    DBSession.add(Log(10387, "join", "room " + str(appstruct['roomNumber'])))
                    transaction.commit()
                elif join_room.points < test_points: # if new people beat out current ocupents
                    old_room = DBSession.query(Room).filter(or_(
                        Room.name1 == appstruct['partnerName'],
                        Room.name2 == appstruct['partnerName'])).first();
                    if not old_room == None: # the other person was already in a room
                        if room.name1 == appstruct['partnerName']:
                            old_room.name1 = None
                        else:
                            old_room.name2 = None
                        # removes the points from the user's old room
                        old_room.points -= conn.get_points_uid(appstruct['partnerName'])
                        DBSession.add(room)
                    if appstruct['partnerName'] == none: # user joined alone
                        # users were kicked
                        if not join_room.name1 == None or not join_room.name2 == None:
                            users = str(join_room.name1) if not join_room.name1 == None else ""
                            if users == "":
                                users = str(join_room.name2)
                            else:
                                users += " & " + str(join_room.name2)
                            DBSession.add(Log(10387, "join",
                                "user join room " + str(appstruct['roomNumber']) + ", kicking " + users))
                        else:
                           DBSession.add(Log(10387, "join", "user joined room alone"))
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
                                    partnerString = name[1]
                                if name[0] == str(join_room.name1):
                                    kickString1 = name[1]
                                if name[0] == str(join_room.name2):
                                    kickString2 = name[1]
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

                            DBSession.add(Log(10387, "join",
                                "room " + str(appstruct['roomNumber']) + " with " +
                                partnerString + ", kicking " + kickString))
                        else: # joined with partner and did not kick anyone
                            for name in names:
                                if name[0] == str(appstruct['partnerName']):
                                    DBSession.add(Log(10387, "join", "room " + str(appstruct['roomNumber']) + " with " +
                                            name[1] + "(" + str(appstruct['partnerName']) + ")"))
                                    break
                            else:
                                DBSession.add(Log(10387, "join", "room " + str(appstruct['roomNumber']) + " with " +
                                    str(appstruct['partnerName'])))
                    partnerRoom = DBSession.query(Room).filter(or_(
                        Room.name1 == appstruct['partnerName'],
                            Room.name2 == appstruct['partnerName'])).first()
                    if partnerRoom:
                        if partnerRoom.name1 == int(appstruct['partnerName']):
                            partnerRoom.name1 = None
                        else:
                            partnerRoom.name2 = None
                        DBSession.add(partnerRoom) # removes the partner from their old room
                    DBSession.query(Room).filter_by(number=appstruct['roomNumber']).update(
                            {"name2": int(appstruct['partnerName'])
                                if not appstruct['partnerName'] == none else None,
                                "name1": 10387, "points": test_points})
                    transaction.commit()
                else:
                    request.session.flash('Warning: You do not have enough housing points')
                    return HTTPFound(location=request.route_url('view_main'))
            request.session.flash('Successfully joined room ' + str(appstruct['roomNumber']))
            return HTTPFound(location=request.route_url('view_main'))
        except deform.ValidationFailure, e:
            conn.close()
            return {'form': e.render(), 'admin': admin}
    else:
        conn.close()
        return {'form': form.render(), 'admin': admin}
