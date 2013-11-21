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

