from flask import Flask, Blueprint
from flask_restful import Api, Resource, url_for

import app
from app import db

api_bp = Blueprint('mod_api', __name__)
api = Api(api_bp)

'''
class TodoItem(Resource):
    def get(self, id):
        return {'task': 'Say "Hello, World!"'}

mod_api.add_resource(TodoItem, '/todos/<int:id>')
app.register_blueprint(api_bp)
'''