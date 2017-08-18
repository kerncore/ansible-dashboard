import logging
import sys
import traceback
from pymongo import MongoClient

from app.mod_issues.extractors import extract_template_sections
from app.mod_issues.extractors import extract_template_data

DBNAME = 'github_api'


class IssueModel(object):

    issueid = None
    is_pullrequest = False
    events = []
    _comments = []
    files = []
    reactions = []

    def __init__(self, issueid):
        self.issueid = issueid
        self.load()

    def load(self):
        client = MongoClient()
        db = getattr(client, DBNAME)

        issue = db.issues.find_one({'id': self.issueid})
        if issue:
            for k,v in issue.items():
                setattr(self, k, v)

            if 'pull' in issue['html_url']:
                self.is_pullrequest = True

                logging.debug('finding PR for {}'.format(issue['url']))
                pull = db.issues.find_one({'issue_url': issue['url']})
                if pull:
                    for k,v in pull.items():
                        if not hasattr(self, k):
                            setattr(self, k, v)
                        else:
                            setattr(self, 'pull_' + k, v)

            logging.debug('finding comments for {}'.format(issue['url']))
            self._comments = db.comments.find({'issue_url': issue['url']})

        client.close()

    @property
    def files(self):
        files = []
        if not self.is_pullrequest:
            return files
        client = MongoClient()
        db = getattr(client, DBNAME)
        pipeline = [
            {'$match': {'issue_url': self.url}}
        ]
        logging.debug('find files for {}'.format(self.url))
        cursor = db.pullrequest_files.aggregate(pipeline)
        files = list(cursor)
        client.close()
        logging.debug('{} files for {}'.format(len(files), self.url))
        return files

    @property
    def template_sections(self):
        section_names = extract_template_sections(self.body)
        logging.debug('section names: {}'.format(section_names))
        logging.debug('extracting template...')
        try:
            sections = extract_template_data(self.body, issue_number=self.number, SECTIONS=section_names)
        except Exception as e:
            sections = {}

        logging.debug('extraction done')
        logging.debug(sections)
        return sections
