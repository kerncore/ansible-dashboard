from flask_wtf import FlaskForm

# Import Form elements such as TextField and BooleanField (optional)
from wtforms import StringField
from wtforms import SelectField
from wtforms import SubmitField


class SearchForm(FlaskForm):
    query = StringField('query')
    submit = SubmitField(label='submit')