import re
import colander
import deform_bootstrap
import deform
import ldap_conn
from docutils.core import publish_parts
from pkg_resources import resource_filename
from deform_bootstrap.widget import ChosenSingleWidget
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.view import view_config
from sqlalchemy.orm.exc import NoResultFound
from .models import DBSession, Room, User
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer
from translationstring import TranslationStringFactory
from ldap_conn import ldap_conn

_ = TranslationStringFactory('deform')
css = HtmlFormatter().get_style_defs('.highlight')

def translator(term):
    return get_localizer(get_current_request()).translate(term)

    deform_template_dir = resource_filename('deform', 'templates/')

    zpt_renderer = deform.ZPTRendererFactory(
                [deform_template_dir], translator=translator)

@view_config(route_name='view_delete')
def view_delete(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard("jd"):
        try:
            DBSession.delete(DBSession.query(Room).filter_by(number = request.matchdict['room_number']).one())
        except NoResultFound, e:
            pass

        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))

@view_config(route_name='view_delete_current')
def view_delete_current(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard("jd"):
        try:
            DBSession.delete(DBSession.query(User).filter_by(name = request.matchdict['name']).one())
        except NoResultFound, e:
            pass

        return HTTPFound(request.route_url('view_admin'))
    else:
        return HTTPFound(request.route_url('view_main'))


@view_config(route_name='view_admin', renderer='templates/admin.pt')
def view_admin(request):
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard("jd"):
        rooms = DBSession.query(Room).all()
        users = DBSession.query(User).all()
        name_map = dict()
        points_map = dict()
        ids = set()
        for room in rooms:
            numbers.append((room.number, room.number))
            numbers_validate.append(room.number)
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

        class New_Room(colander.Schema):
            number = colander.SchemaNode(colander.Integer(), missing = colander.required)
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

        # new room was given
        if ('__start__', u'new_rooms:sequence') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
                for new_room in appstruct['new_rooms']:
                    room = Room(new_room['number'])
                    room.locked = new_room['locked']
                    DBSession.add(room)
                DBSession.flush()
                return HTTPFound(location=request.route_url('view_admin'))
            except deform.ValidationFailure, e:
                return {'name_map': name_map, 'rooms': rooms, 'form': e.render(), 'users': users, 'points_map': points_map, 'current_rooms_form': current_rooms_form.render()}

        # current room was given
        elif ('__start__', u'current_rooms:sequence') in request.POST.items():
            try:
                appstruct = current_rooms_form.validate(request.POST.items())
                for current_room in appstruct['current_rooms']:
                    if DBSession.query(User).filter_by(name = current_room['name']).update({'number': current_room['number']}) == 0:
                        DBSession.add(User(current_room['name'], current_room['number']))
                DBSession.flush()
                users = DBSession.query(User).all()
            except deform.ValidationFailure, e:
                return {'name_map': name_map, 'rooms': rooms, 'form': form.render(), 'users': users, 'points_map': points_map, 'current_rooms_form': e.render()}
        return {'name_map': name_map, 'rooms': rooms, 'form': form.render(), 'users': users, 'points_map': points_map, 'current_rooms_form': current_rooms_form.render()}
    else:
        conn.close()
        return HTTPFound(location=request.route_url('view_main'))

@view_config(route_name='view_admin_edit', renderer='templates/edit.pt')
def view_admin_edit(request):
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])

    if conn.isEBoard("jd"):

        if ('cancel', u'cancel') in request.POST.items():
            return HTTPFound(location=request.route_url('view_admin'))
	    if DBSession.query(Room).filter_by(number=request.matchdict['room_number']).all() == []:
		    return {'form': 'There is no room #' + request.matchdict['room_number']}

        for element in conn.get_active():
            names.append((element[0][1]['uidNumber'][0], element[0][1]['uid'][0]))
            names_validate.append(element[0][1]['uidNumber'][0])

        class Schema(colander.Schema):
            name1 = colander.SchemaNode(
		    	colander.String(),
			    title = 'Roommate #1',
    			widget = ChosenSingleWidget(values=names),
	    		validator = colander.OneOf(names_validate),
		    	missing = colander.required)
            name2 = colander.SchemaNode(
	    		colander.String(),
		    	title = 'Roommate #2',
			    widget = ChosenSingleWidget(values=names),
    			validator = colander.OneOf(names_validate),
	    		missing = colander.required)
            locked = colander.SchemaNode(
			    colander.Bool(),
    			title = 'Locked',
	    		widget = deform.widget.CheckboxWidget())

        schema = Schema()
        form = deform.Form(schema, buttons=('submit', 'cancel'))

        if ('submit', u'submit') in request.POST.items():
            try:
                appstruct = form.validate(request.POST.items())
                DBSession.query(Room).filter_by(number=request.matchdict['room_number']).update({'name1': appstruct['name1'], 'name2': appstruct['name2'], 'locked': appstruct['locked']})
                DBSession.flush()
                return HTTPFound(location=request.route_url('view_admin'))
            except deform.ValidationFailure, e:
                return {'form': e.render(), 'number': request.matchdict['room_number']}
        else:
            return {'form': form.render(), 'number': request.matchdict['room_number']}

    else: # invalid permissions
        return HTTPFound(location=request.route_url('view_main'))


@view_config(route_name='view_main', renderer='templates/index.pt')
def view_main(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])
    rooms = DBSession.query(Room).all()
    name_map = dict()
    ids = []
    next_room = None
    uid_number = conn.get_uid_number("jd")
    for room in rooms:
        print room.name1
        if room.name1 == uid_number:
            next_room = room.name1
        elif room.name2 == uid_number:
            next_room = room.name2
        if room.name1 is not None:
            ids.append(room.name1)
        if room.name2 is not None:
            ids.append(room.name2)
    if not ids == []:
        for user in conn.search_uids(ids):
            name_map[int(user[0][1]['uidNumber'][0])] = user[0][1]['uid'][0]
    try:
        current_room = DBSession.query(User).filter_by(name=conn.get_uid_number("jd")).one().number
    except NoResultFound, e:
        current_room = None
    return {'name_map': name_map, 'rooms': rooms, 'admin': True, 'points': conn.get_points("jd"), 'current':  current_room, 'next_room': next_room}

@view_config(route_name='view_join', renderer='templates/join.pt')
def view_join(request):
    settings = request.registry.settings
    conn = ldap_conn(settings['address'], settings['bind_dn'], settings['password'], settings['base_dn'])
    numbers_validate = []
    names_validate = []
    numbers = []
    names = []
    if ('cancel', u'cancel') in request.POST.items():
        return HTTPFound(location=request.route_url('view_main'))

    for room in DBSession.query(Room).all():
        if not room.locked:
            numbers_validate.append(room.number)
            numbers.append((room.number, room.number))
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
                missing=colander.required)

    schema = Schema()
    form = deform.Form(schema, buttons=('submit', 'cancel'))

    if  ('submit', u'submit') in request.POST.items():
        try:
            appstruct = form.validate(request.POST.items())
            room = Room(appstruct['roomNumber'])
            if DBSession.query(Room).filter_by(number=appstruct['roomNumber']).one().locked:
                return {'form': 'Room is locked'}
            else:
                DBSession.query(Room).filter_by(number=appstruct['roomNumber']).update({"name1": appstruct['partnerName']})
                DBSession.flush()

            return {'form': 'Successfully added to room ' + str(appstruct['roomNumber'])}
        except deform.ValidationFailure, e:
            return {'form': e.render()}
    else:
       return {'form': form.render()}
