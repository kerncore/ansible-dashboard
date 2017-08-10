# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for


# Import password / encryption helper tools
from werkzeug import check_password_hash, generate_password_hash

# Import the database object from the main app module
from app import db

'''
# Import module models (i.e. User)
from app import db
from app.mod_auth.models import User
from app import login_manager
'''

from flask_login import login_required

# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_search = Blueprint('mod_search', __name__, url_prefix='/mod_search')

'''
@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))
'''

@mod_search.route('/', methods=['GET', 'POST'])
@login_required
def index():
    return render_template("mod_search/mod_search.html")