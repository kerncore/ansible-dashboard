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


from app import login_manager
from flask_login import login_user, logout_user, current_user, login_required

# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_auth = Blueprint('auth', __name__, url_prefix='/auth')


# Set the route and accepted methods
@mod_auth.route('/signin/', methods=['GET', 'POST'])
def signin():

    # If sign in form is submitted
    form = LoginForm(request.form)

    # Verify the sign in form
    if form.validate_on_submit():

        user = User.query.filter_by(email=form.email.data).first()

        if user and check_password_hash(user.password, form.password.data):

            session['user_id'] = user.id
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