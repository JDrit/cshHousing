from deform_bootstrap.widget import ChosenSingleWidget, DateTimeInputWidget
import colander
import roommatePair
import user
import deform

class SettingsSchema(colander.Schema):
    send_email = roommate = None

    def __init__(self, uid_number, names, names_validate):
        self.send_email = colander.SchemaNode(
                colander.Bool(),
                title = 'Send Email',
                description = 'This will send emails to your CSH account when changes occur to your housing status',
                widget = deform.widget.CheckboxWidget(),
                default = user.get_send_status(uid_number))
        self.roommate = colander.SchemaNode(
                colander.String(),
                title='Roommate\'s name',
                widget=ChosenSingleWidget(values=names),
                validator=colander.OneOf(names_validate),
                missing=None,
                description = 'You need to set this to whoever you want to be roommates with so that your they will be able to control your housing status. If you do not do this, then no one will be able to sign you up with them',
                default = roommatePair.get_roommate(uid_number))

class NewRoommate(colander.Schema):
    username = roommate = None

    def __init__(self, names, names_validate):
        self.uid_number1 = colander.SchemaNode(
                colander.String(),
                title = 'Roommate 1',
                widget = ChosenSingleWidget(values = names),
                validator = colander.OneOf(names_validate),
                missing = colander.required)
        self.uid_number2 = colander.SchemaNode(
                colander.String(),
                title = 'Roommate 2',
                widget = ChosenSingleWidget(values = names),
                validator = colander.OneOf(names_validate),
                missing = colander.required)

class NewRoom(colander.Schema):
    number = locked = single = None

    def __init__(self, room_numbers):
        self.number = colander.SchemaNode(colander.Integer(),
                missing = colander.required,
                validator = colander.Function(lambda value: not value in room_numbers))
        self.locked = colander.SchemaNode(colander.Bool())
        self.single = colander.SchemaNode(colander.Bool())

class NewRooms(colander.SequenceSchema):
    self.new_room = None

    def __init__(self, room_numbers):
        self.new_room = NewRoom(room_numbers)

class NewRoomsSchema(colander.Schema):
    self.new_rooms = None

    def __init__(self, room_numbers):
        new_rooms = NewRooms(room_numbers)

class CurrentRoom(colander.Schema):
    name = number = None

    def __init__(self, names, names_validate, numbers, numbers_validate):
        self.uid_number = colander.SchemaNode(
                colander.String(),
                title = 'Member\'s Name',
                widget = ChosenSingleWidget(values = names),
                validator = colander.OneOf(names_validate),
                missing = colander.required)
        self.room_number = colander.SchemaNode(
                colander.Integer(),
                title = 'Room Number',
                widget = ChosenSingleWidget(values = numbers),
                validator = colander.OneOf(numbers_validate),
                missing = colander.required)

class CurrentRooms(colander.SequenceSchema):
    current_room = None

    def __init__(self, names, names_validate, numbers, numbers_validate):
        self.current_room = Current_Room(names, names_validate, numbers, numbers_validate)

class CurrentRoomsSchema(colander.Schema):
    current_rooms = None

    def __init__(self, names, names_validate, numbers, numbers_validate):
        current_rooms = CurrentRooms(names, names_validate, numbers, numbers_validate)

class TimeSchema(colander.Schema):
    lock = open_time = close_time = None

    def __init__(self, site_closed, open_time, close_time):
        self.lock = colander.SchemaNode(
                colander.Boolean(),
                missing = colander.required,
                default = site_closed,
                description = "Locks the site so no users can change their status")
        self.open_time = colander.SchemaNode(
                colander.DateTime(),
                widget = DateTimeInputWidget(),
                missing = None,
                default = open_time,
                description = "Auto opens the site at the given time")
        self.close_time = colander.SchemaNode(
                colander.DateTime(),
                widget = DateTimeInputWidget(),
                missing = None,
                default = close_time,
                description = "Auto closes the site at a given time")

class AdminRoomEdit(colander.Schema):
    uid_number1 = uid_number2 = locked = single = None

    def __init__(self, names, names_validate):
        uid_number1 = colander.SchemaNode(
            colander.String(),
            title = 'Roommate #1',
            widget = ChosenSingleWidget(values=names),
            validator = colander.OneOf(names_validate),
            default = room.name1 or empty,
            missing = None)
        uid_number2 = colander.SchemaNode(
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

class JoinSchema(colander.Schema):
    room_number = roommate = None

    def __init__(self, numbers, numbers_validate, names, names_validate):
        self.room_number = colander.SchemaNode(
                colander.Integer(),
                title = 'Room number',
                widget = ChosenSingleWidget(values=numbers),
                validator = colander.OneOf(numbers_validate),
                missing = None,
                default = room_id)
        self.roommate = colander.SchemaNode(
                colander.String(),
                title='Roommate\'s name',
                widget=ChosenSingleWidget(values=names),
                validator=colander.OneOf(names_validate),
                missing=None,
                default = none)

