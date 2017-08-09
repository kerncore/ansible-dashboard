# Import Form and RecaptchaField (optional)
#from flask.ext.wtf import Form

from flask_wtf import FlaskForm

# Import Form elements such as TextField and BooleanField (optional)
from wtforms import TextField, PasswordField # BooleanField
from wtforms import StringField

# Import Form validators
from wtforms.validators import Required, Email, EqualTo
from wtforms.validators import DataRequired

# Define the login form (WTForms)

class LoginForm(FlaskForm):
    email    = StringField('Email Address', [Email(),
                DataRequired(message='Forgot your email address?')])
    password = PasswordField('Password', [
                DataRequired(message='Must provide a password. ;-)')])

class SignupForm(FlaskForm):
    email    = StringField('Email Address', [Email(),
                DataRequired(message='Must be a valid email address.')])
    password = PasswordField('Password', [
                DataRequired(message='Must provide a password. ;-)')])