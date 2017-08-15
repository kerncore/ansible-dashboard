# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for


# Import password / encryption helper tools
from werkzeug import check_password_hash, generate_password_hash

# Import the database object from the main app module
from app import db

import logging
from pymongo import MongoClient


from flask_login import login_required
from app.mod_search.forms import SearchForm


# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_search = Blueprint('mod_search', __name__, url_prefix='/search')

DBNAME = 'github_api'

@mod_search.route('/', methods=['GET', 'POST'])
@login_required
def index():

    results = []
    form = SearchForm()

    if request.method == 'POST':
        query = form.query.data
        logging.debug('query: {}'.format(query))
        client = MongoClient()
        db = getattr(client, DBNAME)
        collection = db.issues

        pipeline = [
            {
                '$project': {
                    '_id': 0,
                    'number': 1,
                    'title': 1
                }
            }
        ]

        logging.debug('pipeline starting')
        cursor = collection.aggregate(pipeline)
        results = list(cursor)
        logging.debug('pipeline finished ({} total)'.format(len(results)))


    return render_template("search/index.html", form=form, results=results)