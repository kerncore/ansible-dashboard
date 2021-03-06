#!/usr/bin/env python3

import logging
#import re
#from operator import itemgetter
#from pprint import pprint
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
    BZDBNAME = 'bugzilla'
    BZCOLLECTIONNAME = 'bugs'
    SFDCDBNAME = 'sfdc'
    SFDCCOLLECTIONNAME = 'cases'

    def __init__(self, repo, number, force=False):
        self.repo = repo
        self.number = number
        self.force = force
        self.repository_url = 'https://api.github.com/repos/{}'.format(self.repo)
        self._comments = []
        self._bugzillas = []
        self._timeline = None

        self._data = {}
        self._old_data = {}

        self.client = MongoClient()
        self.api_db = getattr(self.client, self.API_DBNAME)
        self.index_db = getattr(self.client, self.INDEX_DBNAME)
        self.index_collection = getattr(self.index_db, 'issues')
        self.bzdb = getattr(self.client, self.BZDBNAME)
        self.bzcol = getattr(self.bzdb, self.BZCOLLECTIONNAME)

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
        if '/pull/' in self._data['html_url'] or '/pulls/' in self._data['html_url']:
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

        # mongo doesn't like keys with periods
        topop = []
        for key in section_names.keys():
            if '.' in key:
                topop.append(key)
        if topop:
            for x in topop:
                section_names.pop(x, None)

        try:
            sections = extract_template_data(self.body, issue_number=self.number, SECTIONS=section_names)
        except Exception as e:
            logging.error(e)
            sections = {}
        return sections

    @property
    def url(self):
        return self._data.get('url')

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

        # force a fetch of the comments
        self.comments

        # synthetic
        self._data['template_data'] = self.template_data
        self._data['_comments_bodies'] = self.comments_bodies
        self._data['_comments_users'] = self.comments_users
        self._data['_comments_dates'] = self.comments_dates
        self._data['events_count'] = len(self.events)
        self._data['cross_references'] = self.cross_references
        self._data['cross_references_count'] = len(self._data['cross_references'])
        self._data['files'] = self.files
        self._data['migrated_from'] = self.migrated_from
        self._data['migrated_to'] = self.migrated_to
        self._data['bugzillas'] = self.bugzillas
        self._data['bugzillas_count'] = self.bugzilla_count
        self._data['sfdc_cases'] = self.sfdc_cases
        self._data['sfdc_count'] = len(self._data['sfdc_cases'])
        self._data['timeline'] = self.timeline[:]

        if self.changed:
            logging.debug('{} changed, updating index db'.format(self._data['url']))
            try:
                self.index_collection.replace_one(
                    {'url': self._data['url']}, self._data, True
                )
            except Exception as e:
                logging.error(e)
                import epdb; epdb.st()

    def _get_current_data(self):
        pipeline = [
            {
                '$match': {
                    'url': {
                        '$regex': '^{}/.*/{}$'.format(self.repository_url, self.number)
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
    def bugzilla_count(self):
        return len(self._bugzillas)

    @property
    def issue(self):
        pipeline = [
            {
                '$match': {
                    'url': {
                        '$regex': '^{}/.*/{}$'.format(self.repository_url, self.number)
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
                        '$regex': '^{}/.*/{}$'.format(self.repository_url, self.number)
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
        #import epdb; epdb.st()
        filenames = [x['filename'] for x in files]
        return filenames

    @property
    def comments_users(self):
        if not self._comments:
            return []
        usernames = []
        for comment in self._comments:
            usernames.append(comment['user']['login'])
        return usernames

    @property
    def comments_bodies(self):
        if not self._comments:
            return []
        bodies = []
        for comment in self._comments:
            bodies.append(comment['body'])
        return bodies

    @property
    def comments_dates(self):
        if not self._comments:
            return []
        dates = []
        for comment in self._comments:
            dates.append(comment['created_at'])
        return dates

    @property
    def comments(self):
        #if self._data.get('comments') == 0:
        #    return []

        pipeline = [
            {
                '$match': {
                    'issue_url': {
                        '$regex': '^{}/.*/{}$'.format(self.repository_url, self.number)
                    }
                }
            },
            {'$project': {'_id': 0}}
        ]
        cursor = self.api_db.comments.aggregate(pipeline)
        comments = list(cursor)

        self._comments = comments

        #import epdb; epdb.st()
        return comments

    @property
    def events(self):
        pipeline = [
            {
                '$match': {
                    'issue_url': {
                        '$regex': '^{}/.*/{}$'.format(self.repository_url, self.number)
                    }
                }
            },
            {'$project': {'_id': 0}}
        ]
        cursor = self.api_db.events.aggregate(pipeline)
        events = list(cursor)
        return events

    @property
    def bugzillas(self):
        pipeline = [
            {'$unwind': '$external_bugs'},
            {'$match': {'external_bugs': self._data['html_url']}}
        ]
        cursor = self.bzcol.aggregate(pipeline)
        res = list(cursor)
        self._bugzillas = res
        return res

    @property
    def sfdc_cases(self):
        #SFDCDBNAME = 'bugzilla'
        #SFDCCOLLECTIONNAME = 'bugs'
        sfdc_db = getattr(self.client, self.SFDCDBNAME)
        cases_col = getattr(sfdc_db, self.SFDCCOLLECTIONNAME)

        pipeline = [
            {'$unwind': '$github_issues'},
            {'$match': {'github_issues': self._data['html_url']}}
        ]
        cursor = cases_col.aggregate(pipeline)
        results = list(cursor)

        cases = []
        for res in results:
            if res['url'] not in cases:
                cases.append(res['url'])

        return cases

    @property
    def migrated_from(self):
        # Copied from original issue: ansible/ansible-modules-core#52
        if 'copied from original issue' in self._data['body'].lower():
            import epdb; epdb.st()
        return None

    @property
    def migrated_to(self):
        # This issue was migrated to ansible/ansible#30235
        for comment in self.comments:
            if 'this issue was migrated to' in comment['body'].lower():
                import epdb; epdb.st()
        return None

    @property
    def cross_references(self):
        #import epdb; epdb.st()
        timeline = self.timeline
        filtered = [x for x in timeline if x.get('event') == 'cross-referenced']
        html_urls = [x.get('source', {}).get('issue', {}).get('html_url') for x in filtered]
        html_urls = sorted(set(html_urls))
        return html_urls

    @property
    def timeline(self):
        if self._timeline is None:
            pipeline = [
                {
                    '$match': {
                        'issue_url': {
                            '$regex': '^{}/.*/{}$'.format(self.repository_url, self.number)
                        }
                    }
                },
                {'$project': {'_id': 0}}
            ]
            cursor = self.api_db.timeline.aggregate(pipeline)
            self._timeline = list(cursor)

        return self._timeline


if __name__ == "__main__":
    client = MongoClient()
    db = getattr(client, 'sfdc')
    collection = getattr(db, 'cases')

    reindex = []

    cursor = collection.find()
    res = list(cursor)

    for case in res:
        if not case.get('github_issues'):
            continue
        for url in case['github_issues']:
            if url not in reindex:
                reindex.append(url)

    for idx,rei in enumerate(reindex):
        print('{} of {} -- {}'.format(idx, len(reindex), rei))

        repo = '/'.join(rei.split('/')[3:5])
        if not repo.startswith('ansible') or 'tower' in repo:
            continue
        number = rei.split('/')[-1]
        number = int(number)
        try:
            index = GithubIssueIndex(repo, number, force=True)
        except Exception as e:
            print(e)
        #import epdb; epdb.st()

    import epdb; epdb.st()
