# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for

# Import password / encryption helper tools
from werkzeug import check_password_hash, generate_password_hash

# Import the database object from the main app module
from app import db


from flask_login import login_required


# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_repos = Blueprint('mod_repos', __name__, url_prefix='/repos')


@mod_repos.route('/', methods=['GET', 'POST'])
@login_required
def index():
    return render_template("repos/index.html")