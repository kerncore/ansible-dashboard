# Import the database object (db) from the main application module
# We will define this inside /app/__init__.py in the next sections.

from datetime import datetime

from app import db


# Define a base model for other database tables to inherit
class Base(db.Model):

    __abstract__  = True

    id            = db.Column(db.Integer, primary_key=True)
    date_created  = db.Column(db.DateTime,  default=db.func.current_timestamp())
    date_modified = db.Column(db.DateTime,  default=db.func.current_timestamp(),
                                           onupdate=db.func.current_timestamp())

# Define a User model
class Token(Base):

    __tablename__ = 'tokens'

    id = db.Column('token_id', db.Integer, primary_key=True)
    token = db.Column(db.String(700), nullable=False, unique=True)
    username = db.Column(db.String(700), nullable=False)

    # New instance instantiation procedure
    def __init__(self, username, token):
        self.username = username
        self.token = token

    def get_id(self):
        return unicode(self.id)

    def __str__(self):
        return self.url

    def __iter__(self):
        yield 'id', self.id
        yield 'username', self.username
        yield 'token', self.token

    def __repr__(self):
        return '<Token {}>'.format(self.token)