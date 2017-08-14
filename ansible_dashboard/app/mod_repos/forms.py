from flask_wtf import FlaskForm

# Import Form elements such as TextField and BooleanField (optional)
from wtforms import StringField
from wtforms import SelectField
from wtforms import SubmitField


class NewRepoForm(FlaskForm):
    url = StringField('url')


class RepoControls(FlaskForm):
    #name = StringField(label='Name', validators=[DataRequired()])
    fetch = SubmitField(label='fetch')
    clean = SubmitField(label='clean')
    delete = SubmitField(label='delete')