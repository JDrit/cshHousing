import os
import sys
import transaction

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from ..models import (
    DBSession,
    Room,
    Base,
    )


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)
    config_uri = argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.create_all(engine)
    with transaction.manager:
        for i in [3009, 3012, 3013, 3016, 3020, 3024, 3050, 3051, 3054, 3055, 3059, 3063, 3066, 3067, 3070, 3071, 3086, 3090, 3091, 3094, 3095, 3099, 3103, 3106, 3107, 3110, 3111, 3125, 3126]:
            model = Room(i)
            DBSession.add(model)
    '''
    with transaction.manager:
        model = Page('FrontPage', 'This is the front page')
        DBSession.add(model)
    '''
