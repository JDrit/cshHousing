import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'pyramid',
    'SQLAlchemy',
    'transaction',
    'pyramid_tm',
    'pyramid_debugtoolbar',
    'zope.sqlalchemy',
    'waitress',
    'docutils',
    'colander',
    'deform_bootstrap',
    'deform',
    'pyramid_mailer',
    ]

setup(name='cshHousing',
      version='0.0',
      description='cshHousing',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='JD',
      author_email='jd@csh.rit.edu',
      url='',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='cshhousing',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = cshhousing:main
      [console_scripts]
      initialize_cshHousing_db = cshhousing.scripts.initializedb:main
      """,
      )
