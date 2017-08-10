# Import the database object (db) from the main application module
# We will define this inside /app/__init__.py in the next sections.

from datetime import datetime

from app import db
from werkzeug.security import generate_password_hash

# Define a base model for other database tables to inherit
class Base(db.Model):

    __abstract__  = True

    id            = db.Column(db.Integer, primary_key=True)
    date_created  = db.Column(db.DateTime,  default=db.func.current_timestamp())
    date_modified = db.Column(db.DateTime,  default=db.func.current_timestamp(),
                                           onupdate=db.func.current_timestamp())

# Define a User model
class User(Base):

    __tablename__ = 'auth_user'

    id = db.Column('user_id', db.Integer, primary_key=True)

    # User Name
    #name    = db.Column(db.String(128),  nullable=False)

    # Identification Data: email & password
    email    = db.Column(db.String(128),  nullable=False,
                                            unique=True)
    password = db.Column(db.String(1000),  nullable=False)

    # Authorisation Data: role & status
    role     = db.Column(db.SmallInteger, nullable=False)
    status   = db.Column(db.SmallInteger, nullable=False)

    registered_on = db.Column('registered_on', db.DateTime)

    # New instance instantiation procedure
    def __init__(self, email, password):

        #self.name     = name
        self.email    = email
        self.password = generate_password_hash(password)
        self.registered_on = datetime.utcnow()

    def get_id(self):
        return unicode(self.id)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def __repr__(self):
        return '<User %r>' % (self.email)