# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for


# Import password / encryption helper tools
from werkzeug import check_password_hash, generate_password_hash

# Import the database object from the main app module
from app import db

# Import module forms
from app.mod_auth.forms import LoginForm
from app.mod_auth.forms import SignupForm

# Import module models (i.e. User)
from app import db
from app.mod_auth.models import User

'''
# Does this work?
from flask.ext.login import LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.signin'
'''
from app import login_manager
from flask.ext.login import login_user, logout_user, current_user, login_required

# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_auth = Blueprint('auth', __name__, url_prefix='/auth')

from functools import wraps
from pprint import pprint

'''
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('auth.signin', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
'''

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


# Set the route and accepted methods
@mod_auth.route('/signin/', methods=['GET', 'POST'])
def signin():

    # If sign in form is submitted
    form = LoginForm(request.form)

    # Verify the sign in form
    if form.validate_on_submit():

        user = User.query.filter_by(email=form.email.data).first()
        pprint(user)
        pprint(form.email.data)
        pprint(form.password.data)
        pprint(check_password_hash(user.password, form.password.data))
        pprint('{} != {}'.format(user.password, form.password.data))
        pprint('{} != {}'.format(type(user.password), type(form.password.data)))

        if user and check_password_hash(user.password, form.password.data):

            session['user_id'] = user.id
            pprint(session)

            flash('Welcome %s' % user.email)

            return redirect(url_for('auth.home'))

        flash('Wrong email or password', 'error-message')

    return render_template("auth/signin.html", form=form)


@mod_auth.route('/signup/', methods=['GET', 'POST'])
def signup():

    # If sign up form is submitted
    form = SignupForm(request.form)

    # Verify the sign up form
    if form.validate_on_submit():

        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash('email address is already in use', 'error-message')
        else:
            user = User(form.email.data, form.password.data)
            user.role = 1
            user.status = 1
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('auth.signin'))

    return render_template("auth/signup.html", form=form)


@mod_auth.route('/home/', methods=['GET', 'POST'])
@login_required
def home():
    return render_template("auth/home.html")