# Import flask and template operators
from flask import Flask, render_template

# Import bootstrap
from flask_bootstrap import Bootstrap

# Import SQLAlchemy
from flask_sqlalchemy import SQLAlchemy

# Import login manager
from flask_login import LoginManager

from flask import send_from_directory

# Define the WSGI application object
app = Flask(__name__)

# Configurations
app.config.from_object('config')

# Bootstrap
Bootstrap(app)

# Define the database object which is imported
# by modules and controllers
db = SQLAlchemy(app)

# set the login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.signin'

from app.mod_auth.models import User

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Sample HTTP error handling
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

# Import a module / component using its blueprint handler variable (mod_auth)
from app.mod_api.controllers import mod_api_bp as api_module
from app.mod_auth.controllers import mod_auth as auth_module
from app.mod_repos.controllers import mod_repos as repos_module
from app.mod_search.controllers import mod_search as search_module
from app.mod_tokens.controllers import mod_tokens as tokens_module

# Register blueprint(s)
app.register_blueprint(api_module)
app.register_blueprint(auth_module)
app.register_blueprint(repos_module)
app.register_blueprint(search_module)
app.register_blueprint(tokens_module)


# Build the database:
# This will create the database file using SQLAlchemy
db.create_all()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)