# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for


# Import password / encryption helper tools
from werkzeug import check_password_hash, generate_password_hash

# Import the database object from the main app module
from app import db

import logging
from operator import itemgetter
from pymongo import MongoClient


from flask_login import login_required
from app.mod_search.forms import SearchForm
from app.mod_search.queryparser import QueryParser


# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_search = Blueprint('mod_search', __name__, url_prefix='/search')

DBNAME = 'github_api'

@mod_search.route('/', methods=['GET', 'POST'])
@login_required
def index():

    results = []
    form = SearchForm()

    if request.method == 'POST':

        client = MongoClient()
        db = getattr(client, DBNAME)

        # chop out t he query
        query = form.query.data

        # build the pipelines
        qp = QueryParser()
        collections,pipeline,sortby = qp.parse_to_pipeline(query)

        for collection_name in collections:
            logging.debug('collection: {}'.format(collection_name))
            logging.debug('pipeline: {}'.format(pipeline))
            collection = getattr(db, collection_name)
            cursor = collection.aggregate(pipeline)
            res = list(cursor)
            logging.debug(len(res))
            if res:
                results += res

        client.close()

        if sortby and results:
            logging.debug('sortby: {}'.format(sortby))
            results = [x for x in results if x and sortby[0] in x]
            try:
                if sortby[1] == 'asc':
                    results = sorted(results, key=itemgetter(sortby[0]), reverse=True)
                else:
                    results = sorted(results, key=itemgetter(sortby[0]), reverse=False)
            except Exception as e:
                logging.error(e)

        logging.debug('{} --> {} results'.format(query, len(results)))

    return render_template("search/index.html", form=form, results=results)