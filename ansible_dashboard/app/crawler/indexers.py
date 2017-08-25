import logging
import re
from operator import itemgetter
from pprint import pprint
from pymongo import MongoClient


from app.crawler.extractors import extract_template_sections
from app.crawler.extractors import extract_template_data


def merge_issue_pullrequest(issue, pullrequest):
    rdata = issue.copy()
    for k, v in pullrequest.items():
        if k not in rdata:
            rdata[k] = v
        else:
            rdata['pull_{}'.format(k)] = v
    #import epdb; epdb.st()
    return rdata

class GithubIssueIndex(object):
    API_DBNAME = 'github_api'
    INDEX_DBNAME = 'github_indexes'

    def __init__(self, repo, number, force=False):
        self.repo = repo
        self.number = number
        self.force = force
        self.repository_url = 'https://api.github.com/repos/{}'.format(self.repo)

        self._data = {}
        self._old_data = {}

        self.client = MongoClient()
        self.api_db = getattr(self.client, self.API_DBNAME)
        self.index_db = getattr(self.client, self.INDEX_DBNAME)
        self.index_collection = getattr(self.index_db, 'issues')

        self.build()

    @property
    def changed(self):
        if self._data != self._old_data:
            return True
        else:
            return False

    @property
    def body(self):
        return self._data.get('body')

    @property
    def is_pullrequest(self):
        if '/pull/' in self._data['url'] or '/pulls/' in self._data['url']:
            return True
        else:
            return False

    @property
    def is_issue(self):
        if '/pull/' not in self._data['url'] and '/pulls/' not in self._data['url']:
            return True
        else:
            return False

    @property
    def state(self):
        return self._data.get('state')

    @property
    def template_data(self):
        section_names = extract_template_sections(self.body)
        try:
            sections = extract_template_data(self.body, issue_number=self.number, SECTIONS=section_names)
        except Exception as e:
            sections = {}
        return sections

    def build(self, force=False):

        # what do we currently have?
        self._old_data = self._get_current_data()

        # make a new dataset
        self._data = merge_issue_pullrequest(self.issue, self.pullrequest)
        if not self.force:
            if not self.is_pullrequest:
                if self._data.get('updated_at') == self._old_data.get('updated_at'):
                    return
            elif self._data.get('pull_updated_at') == self._old_data.get('pull_updated_at'):
                return

        # synthetic
        self._data['template_data'] = self.template_data
        self._data['_comments'] = self.comments
        self._data['_comments_users'] = self.comments_users
        self._data['events'] = self.events
        self._data['files'] = self.files

        if self.changed:
            logging.debug('{} changed, updating index db'.format(self._data['url']))
            self.index_collection.replace_one(
                {'url': self._data['url']}, self._data, True
            )

    def _get_current_data(self):
        pipeline = [
            {
                '$match': {
                    'url': {
                        '$regex': '^{}/.*/{}'.format(self.repository_url, self.number)
                    }
                }
            },
            {'$project': {'_id': 0}}
        ]
        cursor = self.index_collection.aggregate(pipeline)
        issues = list(cursor)
        if issues:
            return issues[0]
        else:
            return {}

    @property
    def issue(self):
        pipeline = [
            {
                '$match': {
                    'url': {
                        '$regex': '^{}/.*/{}'.format(self.repository_url, self.number)
                    }
                }
            },
            {'$project': {'_id': 0}}
        ]
        cursor = self.api_db.issues.aggregate(pipeline)
        issues = list(cursor)
        if issues:
            return issues[0]
        else:
            return {}

    @property
    def pullrequest(self):
        pipeline = [
            {
                '$match': {
                    'url': {
                        '$regex': '^{}/.*/{}'.format(self.repository_url, self.number)
                    }
                }
            },
            {'$project': {'_id': 0}}
        ]
        cursor = self.api_db.pullrequests.aggregate(pipeline)
        issues = list(cursor)
        if issues:
            return issues[0]
        else:
            return {}

    @property
    def files(self):
        files = []
        if not self.is_pullrequest:
            return files
        pipeline = [
            {'$match': {'issue_url': self.url}}
        ]
        logging.debug('find files for {}'.format(self.url))
        cursor = self.api_db.pullrequest_files.aggregate(pipeline)
        files = list(cursor)
        logging.debug('{} files for {}'.format(len(files), self.url))
        return files

    @property
    def comments_users(self):
        if not self._data['_comments']:
            return []
        usernames = []
        for comment in self._data['_comments']:
            usernames.append(comment['user']['login'])
        return usernames

    @property
    def comments(self):
        if self._data.get('comments') == 0:
            return []

        pipeline = [
            {
                '$match': {
                    'issue_url': {
                        '$regex': '^{}/.*/{}'.format(self.repository_url, self.number)
                    }
                }
            },
            {'$project': {'_id': 0}}
        ]
        cursor = self.api_db.comments.aggregate(pipeline)
        comments = list(cursor)
        return comments

    @property
    def events(self):
        pipeline = [
            {
                '$match': {
                    'issue_url': {
                        '$regex': '^{}/.*/{}'.format(self.repository_url, self.number)
                    }
                }
            },
            {'$project': {'_id': 0}}
        ]
        cursor = self.api_db.events.aggregate(pipeline)
        events = list(cursor)
        return events