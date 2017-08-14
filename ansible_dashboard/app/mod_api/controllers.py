from flask import Flask, Blueprint
from flask_restful import Api, Resource, url_for, reqparse


from flask_login import login_required

#import app
from app import db

#api_bp = Blueprint('mod_api', __name__, url_prefix='/api')
#mod_api = Api(api_bp)

from app.mod_repos.models import Repo

mod_api_bp = Blueprint('mod_api', __name__, url_prefix='/api')
api = Api(mod_api_bp)


class Repos(Resource):
    @login_required
    def get(self):
        repos = [dict(x) for x in Repo.query.all()]
        return repos

    @login_required
    def post(self):
        pass

api.add_resource(Repos, '/repos', '/repo/<int:id>')