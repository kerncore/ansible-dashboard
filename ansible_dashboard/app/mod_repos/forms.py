from flask_wtf import FlaskForm

# Import Form elements such as TextField and BooleanField (optional)
from wtforms import StringField
from wtforms import SelectField


class NewRepoForm(FlaskForm):
    url = StringField('url')

