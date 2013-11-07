from pyramid.config import Configurator
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from sqlalchemy import engine_from_config
from .models import DBSession, Base
import ConfigParser
import ldap_conn


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    config = Configurator(settings=settings, session_factory = UnencryptedCookieSessionFactoryConfig('itsaseekreet'))


    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('view_main', '/')
    config.add_route('view_join', '/join')
    config.add_route('view_join1', '/join/{room_number}')
    config.add_route('view_admin', '/admin')
    config.add_route('view_admin_edit', '/edit/{room_number}')
    config.add_route('view_delete_current', '/delete_current/{name}')
    config.add_route('view_leave', '/leave')
    config.add_route('view_delete_logs', '/delete_logs')
    config.add_route('view_settings', '/settings')
    config.add_route('view_no_webauth', '/no_webauth')
    config.scan()
    return config.make_wsgi_app()
