# Import the database object (db) from the main application module
# We will define this inside /app/__init__.py in the next sections.

from datetime import datetime
#from urlparse import urlparse
from urllib.parse import urlparse

import logging
from app import db

from app.tasks import update_github_repo_issues

# Define a base model for other database tables to inherit
class Base(db.Model):

    __abstract__  = True

    id            = db.Column(db.Integer, primary_key=True)
    date_created  = db.Column(db.DateTime,  default=db.func.current_timestamp())
    date_modified = db.Column(db.DateTime,  default=db.func.current_timestamp(),
                                           onupdate=db.func.current_timestamp())

# Define a User model
class Repo(Base):

    __tablename__ = 'repos'

    id = db.Column('repo_id', db.Integer, primary_key=True)

    # ansible/ansible jctanner/foo jctanner/bar
    url = db.Column(db.String(700), nullable=False, unique=True)

    # New instance instantiation procedure
    def __init__(self, url):
        self.url = url

    @property
    def hostname(self):
        return urlparse(self.url).netloc

    @property
    def path(self):
        return urlparse(self.url).path.lstrip('/')

    def get_id(self):
        return unicode(self.id)

    def __str__(self):
        return self.url

    def __iter__(self):
        yield 'id', self.id
        yield 'url', self.url
        yield 'created', self.date_created.isoformat()
        yield 'modified', self.date_modified.isoformat()

    def __repr__(self):
        return '<Repo {}>'.format(self.url)

    def fetch(self, issues=[]):
        logging.info('fetching {}'.format(self.url))
        logging.info('{}'.format(self.hostname))
        logging.info('{}'.format(self.path))
        #print(self.hostname)
        if self.hostname.startswith('github.com'):
            update_github_repo_issues.delay(self.path, issues=issues)

    def counts(self):
        data = {
            'total': 0,
            'issues_open': 0,
            'issues_closed': 0,
            'pullrequests_open': 0,
            'pullrequests_closed': 0
        }
        return data