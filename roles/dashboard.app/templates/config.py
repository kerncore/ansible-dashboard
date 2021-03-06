# Statement for enabling the development environment
DEBUG = True

# Define the application directory
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# http://flask-sqlalchemy.pocoo.org/2.1/config/
# Define the database - we are working with
# SQLite for this example

SQLALCHEMY_TRACK_MODIFICATIONS = True

#SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')

#SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/app.db'
#DATABASE_CONNECT_OPTIONS = {}

SQLALCHEMY_DATABASE_URI = 'mysql://dashboard:dashboard@localhost/dashboard'
DATABASE_CONNECT_OPTIONS = {}


# Application threads. A common general assumption is
# using 2 per available processor cores - to handle
# incoming requests using one and performing background
# operations using the other.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)*
CSRF_ENABLED = True

# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = "secret"

# Secret key for signing cookies
SECRET_KEY = "secret"

# LOGIN W/ GITHUB
DATABASE_URI = '{{ DATABASE_URL }}'
DEBUG = True
GITHUB_CLIENT_ID = '{{ GITHUB_CLIENT_ID }}'
GITHUB_CLIENT_SECRET = '{{ GITHUB_CLIENT_SECRET }}'
