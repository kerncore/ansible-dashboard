# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for

# Import the database object from the main app module
from app import db
from app.mod_repos.models import Repo
from app.mod_repos.forms import NewRepoForm


from flask_login import login_required


# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_repos = Blueprint('mod_repos', __name__, url_prefix='/repos')


@mod_repos.route('/', methods=['GET', 'POST'])
@login_required
def index():

    form = NewRepoForm()

    if request.method == 'POST':
        if form.validate() == False:
            flash('All fields are required.')
        else:
            thisrepo = Repo(form.url.data)
            db.session.add(thisrepo)
            db.session.commit()
            #return 'Form posted.'

    repos = Repo.query.all()
    return render_template("repos/index.html", repos=repos, form=NewRepoForm())