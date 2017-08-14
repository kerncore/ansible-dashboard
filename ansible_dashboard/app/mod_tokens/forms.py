from flask_wtf import FlaskForm

# Import Form elements such as TextField and BooleanField (optional)
from wtforms import StringField
from wtforms import IntegerField
from wtforms import SelectField


class NewTokenForm(FlaskForm):
    username = StringField('username', description='username', render_kw={"placeholder": "username"})
    token = StringField('token', description='token', render_kw={"placeholder": "token"})


class DeleteTokenForm(FlaskForm):
    tokenid = IntegerField('tokenid', description='tokenid')
