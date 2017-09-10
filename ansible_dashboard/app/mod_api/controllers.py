from flask import Flask, Blueprint
from flask_restful import Api, Resource, url_for, reqparse

#from flask_login import login_required
from app.login_tools import login_required

from celery.task.control import inspect

#import app
from app import db

from app.mod_repos.models import Repo
from app.mod_tokens.models import Token

mod_api_bp = Blueprint('mod_api', __name__, url_prefix='/api')
api = Api(mod_api_bp)


class JobList(Resource):
    @login_required
    def get(self):

        res = inspect()
        rdata = {
            'active': res.active(),
            'scheduled': res.scheduled(),
            'reserved': res.reserved(),
            'stats': res.stats()
        }
        return rdata

    @login_required
    def post(self):
        pass


class RepoListResource(Resource):
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


class TokenListResource(Resource):
    @login_required
    def get(self):
        repos = [dict(x) for x in Token.query.all()]
        return repos

    @login_required
    def post(self):
        pass


api.add_resource(JobList, '/jobs')
api.add_resource(RepoListResource, '/repos')
api.add_resource(RepoResource, '/repos/<repoid>')
api.add_resource(TokenListResource, '/tokens')
