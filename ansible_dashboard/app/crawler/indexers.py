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
    return rdata

class GithubIssueIndex(object):
    API_DBNAME = 'github_api'
    INDEX_DBNAME = 'github_indexes'

    def __init__(self, repo, number):
        self.repo = repo
        self.number = number
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


    def build(self):

        # what do we currently have?
        self._old_data = self._get_current_data()

        # make a new dataset
        issue = self._get_issue()
        pullrequest = self._get_pullrequest()
        self._data = merge_issue_pullrequest(issue, pullrequest)

        # synthetic
        self._data['template_data'] = self.template_data
        self._data['files'] = self.files
        import epdb; epdb.st()

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

    def _get_issue(self):
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

    def _get_pullrequest(self):
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