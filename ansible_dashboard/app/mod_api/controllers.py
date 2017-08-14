from flask import Flask, Blueprint
from flask_restful import Api, Resource, url_for, reqparse


from flask_login import login_required

#import app
from app import db

from app.mod_repos.models import Repo

mod_api_bp = Blueprint('mod_api', __name__, url_prefix='/api')
api = Api(mod_api_bp)


class ReposResource(Resource):
    @login_required
    def get(self):
        repos = [dict(x) for x in Repo.query.all()]
        return repos

    @login_required
    def post(self):
        pass

class RepoResource(Resource):
    @login_required
    def get(self, repoid):
        repoid = int(repoid)
        thisrepo = Repo.query.filter(Repo.id==repoid).first()
        data = dict(thisrepo)
        return data

    @login_required
    def post(self):
        pass



api.add_resource(ReposResource, '/repos')
api.add_resource(RepoResource, '/repos/<repoid>')