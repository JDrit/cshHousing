import re
import colander
import deform_bootstrap
import deform
import ldap_conn
import datetime
import transaction
from docutils.core import publish_parts
from pkg_resources import resource_filename
from deform_bootstrap.widget import ChosenSingleWidget
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

_ = TranslationStringFactory('deform')
css = HtmlFormatter().get_style_defs('.highlight')

siteClosed = False

def translator(term):
    return get_localizer(get_current_request()).translate(term)

    deform_template_dir = resource_filename('deform', 'templates/')

    zpt_renderer = deform.ZPTRendererFactory(
                [deform_template_dir], translator=translator)

@view_config(context=HTTPNotFound, renderer='templates/404.pt')
def view_404(request):
    return {}

@view_config(route_name='view_delete_logs')
def view_delete_logs(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'],
            settings['password'], settings['base_dn'])
    if conn.isEBoard("jd"):
        DBSession.query(Log).delete()
        transaction.commit()
        conn.close()
        return HTTPFound(request.route_url('view_admin'))
    else:
        conn.close()
        return HTTPFound(request.route_url('view_main'))


@view_config(route_name='view_delete')
def view_delete(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'],
            settings['password'], settings['base_dn'])

    if conn.isEBoard("jd"):
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

    if conn.isEBoard("jd"):
        try:
            DBSession.delete(DBSession.query(User).filter_by(name =
                request.matchdict['name']).one())
            request.session.flash("Successfully deleated current room assignment")
            DBSession.add(Log(10387, "delete current", str(request.matchdict['name'] +
                "'s current room was deleted")))
            transaction.commit()
        except NoResultFound, e:
            request.session.flash("Warning: could not delete current room assignment")
            pass

        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_close')
def view_close(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'],
            settings['password'], settings['base_dn'])
    global siteClosed
    if conn.isEBoard("jd"):
        siteClosed = not siteClosed
        if siteClosed:
            request.session.flash("Site is now closed")
            DBSession.add(Log(10387, "locked", "site was locked"))
        else:
            request.session.flash("Site is now open")
            DBSession.add(Log(10387, "unlocked", "site was unlocked"))
        transaction.commit()
        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))


@view_config(route_name='view_admin', renderer='templates/admin.pt')
def view_admin(request):
    global siteClosed
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard("jd"):
        rooms = DBSession.query(Room).all()
        users = DBSession.query(User).all()
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
        for user in users:
            ids.add(user.name)
        if not ids == set():
            for user in conn.search_uids(list(ids)):
                name_map[int(user[0][1]['uidNumber'][0])] = user[0][1]['uid'][0]
                points_map[int(user[0][1]['uidNumber'][0])] = 5 #user[0][1]['housingPoints'][0]

        for element in conn.get_active():
            names.append((element[0][1]['uidNumber'][0], element[0][1]['uid'][0]))
            names_validate.append(element[0][1]['uidNumber'][0])

        conn.close()

        def notIn(value):
            """
            Makes sure that the room number is not already in use
            value: the new room number
            """
            return not value in room_numbers

        class New_Room(colander.Schema):
            number = colander.SchemaNode(colander.Integer(), missing = colander.required, validator = colander.Function(notIn))
            locked = colander.SchemaNode(colander.Bool())

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

        schema = New_Rooms_Schema()
        form = deform.Form(schema, buttons=('submit',))
        form['new_rooms'].widget = deform.widget.SequenceWidget(min_len=1)
        current_rooms_schema = Current_Rooms_Schema()
        current_rooms_form = deform.Form(current_rooms_schema, buttons=('submit',))
        msgs = request.session.pop_flash()
        logs = DBSession.query(Log).limit(100).all()
        logs.reverse()
        # new room was given
        if ('__start__', u'new_rooms:sequence') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
                rooms_added = 0
                for new_room in appstruct['new_rooms']:
                    if not new_room['number'] in room_numbers:
                        room = Room(new_room['number'])
                        room.locked = new_room['locked']
                        DBSession.add(room)
                        room_numbers.add(new_room['number'])
                        rooms_added += 1
                DBSession.add(Log(10387, "new room added",
                    "added " + str(rooms_added) + " new rooms"))
                transaction.commit()
                if len(appstruct['new_rooms']) > 1:
                    msgs.append('Successfully added ' + str(rooms_added) +
                            ' new rooms')
                else:
                    msgs.append('Successfully added the new room')

            except deform.ValidationFailure, e:
                msgs.append('Warning: could not added new rooms')
                return {'name_map': name_map, 'rooms': rooms, 'form': e.render(),
                        'users': users, 'points_map': points_map,
                        'current_rooms_form': current_rooms_form.render(), 'msgs': msgs,
                        'locked': siteClosed, 'logs': logs}

        # current room was given
        elif ('__start__', u'current_rooms:sequence') in request.POST.items():
            try:
                appstruct = current_rooms_form.validate(request.POST.items())
                rooms_added = 0
                for current_room in appstruct['current_rooms']:
                    if DBSession.query(User).filter_by(name =
                            current_room['name']).update(
                                    {'number': current_room['number']}) == 0:
                        DBSession.add(User(current_room['name'], current_room['number']))
                        rooms_added += 1
                DBSession.add(Log(10387, "current room added",
                    "added " + str(rooms_added) + "  current rooms"))
                transaction.commit()
                users = DBSession.query(User).all()
                msgs.append('Successfully added current room')
            except deform.ValidationFailure, e:
                msgs.append('Warning: Could not add current room assignment')
                return {'name_map': name_map, 'rooms': rooms, 'form': form.render(),
                        'users': users, 'points_map': points_map,
                        'current_rooms_form': e.render(), 'msgs': msgs,
                        'locked': siteClosed, 'logs': logs}
        return {'name_map': name_map, 'rooms': rooms, 'form': form.render(), 'users': users,
                'points_map': points_map, 'current_rooms_form': current_rooms_form.render(),
                'msgs': msgs, 'locked': siteClosed, 'logs': logs}
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

    if conn.isEBoard("jd"):

        if ('cancel', u'cancel') in request.POST.items():
            return HTTPFound(location=request.route_url('view_admin'))
        room = DBSession.query(Room).filter_by(number=request.matchdict['room_number']).all()
        if room == []:
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
                default = room[0].name1 or empty)
            name2 = colander.SchemaNode(
	    		colander.String(),
		    	title = 'Roommate #2',
			    widget = ChosenSingleWidget(values=names),
    			validator = colander.OneOf(names_validate),
                default = room[0].name2 or empty)
            locked = colander.SchemaNode(
			    colander.Bool(),
    			title = 'Locked',
	    		widget = deform.widget.CheckboxWidget(),
                default = room[0].locked)

        schema = Schema()
        form = deform.Form(schema, buttons=('submit', 'cancel'))

        if ('submit', u'submit') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
                name1 = appstruct['name1'] if not appstruct['name1'] == empty else None
                name2 = appstruct['name2'] if not appstruct['name2'] == empty else None
                points = sum(conn.get_points_uidNumbers([name1, name2]).values())
                if not DBSession.query(User).filter(or_(
                    and_(User.name == name1, User.number == request.matchdict['room_number']),
                    and_(User.name == name2, User.number == request.matchdict['room_number'])
                    )).first() == None:
                    points += .5

                DBSession.query(Room).filter_by(number=
                        request.matchdict['room_number']).update({'name1': name1,
                            'name2': name2, 'locked': appstruct['locked'], 'points': points})
                DBSession.add(Log(10387, "edit", "edited room " +
                    str(request.matchdict['room_number']) + " from " +
                    str(room[0].name1 or "None") + ", " + str(room[0].name2) + " to " +
                    str(name1 or "None") + ", " + str(name2 or "None")))
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
    global siteClosed
    session = request.session
    msgs = session.pop_flash()
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])
    rooms = DBSession.query(Room).all()
    name_map = dict()
    ids = []
    next_room = None
    uid_number = conn.get_uid_number("jd")
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
    current_room = DBSession.query(User).filter_by(name=conn.get_uid_number("jd")).first()
    current_room = current_room.number if not current_room == None else None
    return {'name_map': name_map, 'rooms': rooms, 'admin': True, 'points': conn.get_points_uid("jd"), 'current':  current_room, 'next_room': next_room, 'msgs': msgs, 'locked': siteClosed}

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

    if siteClosed:
        return HTTPFound(location=request.route_url('view_main'))

    if ('cancel', u'cancel') in request.POST.items():
        return HTTPFound(location=request.route_url('view_main'))

    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    uidNumber = conn.get_uid_number("jd")
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

                test_points += results.get(appstruct['partnerName']) or 0
                test_points += results.get(10387) or 0
                # squatting points
                if not DBSession.query(User).filter(or_(
                    and_(User.name == appstruct['partnerName'],
                        User.number == appstruct['roomNumber']),
                    and_(User.name == 10387, User.number == appstruct['roomNumber']))
                    ).first() == None:
                    test_points += .5

                if join_room.points < test_points: # if new people beat out current ocupents
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
                            users = str(join_room.name1) if not join_room.name1 == None else ""
                            if users == "":
                                users = str(join_room.name2)
                            else:
                                users += " & " + str(join_room.name2)
                            DBSession.add(Log(10387, "join",
                                "user joined room " + str(appstruct['roomNumber']) + " with " +
                                str(appstruct['partnerName']) + ", kicking " + users))
                        else:
                            DBSession.add(Log(10387, "join", "user joined room with " +
                                str(appstruct['partnerName'])))

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
            return {'form': e.render()}
    else:
       return {'form': form.render()}
