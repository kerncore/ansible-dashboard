# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for


# Import password / encryption helper tools
from werkzeug import check_password_hash, generate_password_hash

# Import the database object from the main app module
from app import db

import logging

from flask_login import login_required
from app.mod_search.forms import SearchForm

from app.mod_search.queryexecutor import QueryExecutor


# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_search = Blueprint('mod_search', __name__, url_prefix='/search')

DBNAME = 'github_api'


@mod_search.route('/', methods=['GET', 'POST'])
@login_required
def index():

    results = []
    form = SearchForm()

    if request.method == 'POST':

        # chop out the query
        query = form.query.data

        # run the query
        qe = QueryExecutor()
        results = qe.runquery(query)
        logging.debug('{} --> {} results'.format(query, len(results)))

    return render_template("search/index.html", form=form, results=results)