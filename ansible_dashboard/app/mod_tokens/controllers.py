# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, redirect

# Import the database object from the main app module
from app import db
#from app.mod_repos.models import Repo
#from app.mod_repos.forms import NewRepoForm

from app.mod_tokens.models import Token
from app.mod_tokens.forms import NewTokenForm
from app.mod_tokens.forms import DeleteTokenForm


#from flask_login import login_required
from app.login_tools import login_required


# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_tokens = Blueprint('mod_tokens', __name__, url_prefix='/tokens')


@mod_tokens.route('/', methods=['GET', 'POST'])
@login_required
def index():

    form = NewTokenForm()

    if request.method == 'POST':
        if form.validate() is False:
            flash('All fields are required.')
        else:
            thistoken = Token(form.username.data, form.token.data)
            db.session.add(thistoken)
            db.session.commit()

    #repos = Repo.query.all()
    return render_template("tokens/index.html", form=form)


@mod_tokens.route('/<int:tokenid>', methods=['GET', 'POST'])
@login_required
def tokenview(tokenid):
    form = DeleteTokenForm()

    if request.method == 'POST':

        thistoken = Token.query.filter(Token.id == tokenid).first()
        db.session.delete(thistoken)
        db.session.commit()

        #return url_for('mod_tokens')
        return redirect('/tokens')

    token = Token.query.filter(Token.id == tokenid).first()
    return render_template("tokens/tokenview.html", token=token, form=form)
