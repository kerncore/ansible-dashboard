#!/usr/bin/env ptyhon3

import hashlib
import logging
import os
import random
import requests
import sys
import time
import timeout_decorator

from natsort import natsorted
from natsort import ns
from operator import itemgetter
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from app.crawler.ghgraphql import GithubGraphQLClient
from app.crawler.indexers import GithubIssueIndex

#from pprint import pprint

'''
root = logging.getLogger()
root.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
root.addHandler(ch)
'''


class GHCrawler(object):

    DBNAME = 'github_api'

    def __init__(self, tokens):
        self.tokens = tokens
        self.gql = GithubGraphQLClient(self.tokens[0])
        self.client = MongoClient()
        self.db = getattr(self.client, self.DBNAME)

        self.headermap = {}

    @staticmethod
    def cleanlinks(links):
        linkmap = {}
        links = links.split(',')
        for idl, link in enumerate(links):
            parts = link.split(';')
            parts = [x.strip() for x in parts if x.strip()]
            parts[0] = parts[0].replace('<', '').replace('>', '')
            rel = parts[1].split('"')[1]
            linkmap[rel] = parts[0]
        return linkmap

    @timeout_decorator.timeout(5)
    def call_requests(self, url, headers):
        return requests.get(url, headers=headers)

    def _geturl(self, url, parent_url=None, since=None, conditional=True, follow=True):

        if since:
            _url = url + '?since=%s' % since
        else:
            _url = url

        # for paginated requests, resume at the last page
        if conditional and follow:
            pipeline = [
                {'$match': {'parent_url': url}},
                {'$project': {'_id': 0, 'url': 1}}
            ]
            cursor = self.db.headers.aggregate(pipeline)
            res = list(cursor)
            if res:
                res = [x['url'] for x in res]
                res = natsorted(res, key=lambda y: y.lower())
                url = res[-1]

        token = random.choice(self.tokens)
        accepts = [
            'application/vnd.github.squirrel-girl-preview',
            'application/vnd.github.mockingbird-preview'
        ]
        headers = {
            'Authorization': 'token {}'.format(token),
            'User-Agent': 'Awesome Octocat-App',
            'Accept': ','.join(accepts)
        }
        print(headers)

        # https://developer.github.com/v3/#conditional-requests
        if _url not in self.headermap:
            db_headers = self.db.headers.find_one({'url': _url}) or {}
        else:
            db_headers = self.headermap.get(_url, {})

        if db_headers and conditional:
            if db_headers.get('ETag'):
                headers['If-None-Match'] = db_headers['ETag']
            else:
                headers['If-Modified-Since'] = db_headers['Date']

        # use the same credentials for this every time
        if db_headers.get('Authorization'):
            headers['Authorization'] = db_headers['Authorization']

        rr = None
        success = False
        while not success:
            try:
                #rr = requests.get(_url, headers=headers)
                rr = self.call_requests(_url, headers)
            except requests.exceptions.ConnectionError:
                logging.warning('sleeping {}s due to connection error'.format(60*2))
                time.sleep(60*2)
                continue
            except timeout_decorator.timeout_decorator.TimeoutError:
                logging.warning('sleeping {}s due to timeout'.format(60*2))
                time.sleep(60*2)
                continue

            if rr.status_code < 400:
                success = True
                break
            if rr.status_code == 404:
                # a missing issue
                success = True
                break

            if rr.status_code == 401:
                success = False
                break
                #import epdb; epdb.st()

            jdata = {}
            try:
                jdata = rr.json()
            except Exception as e:
                logging.error(e)

            if 'api rate limit exceeded' in jdata.get('message', '').lower():
                if 'X-RateLimit-Reset' in rr.headers:
                    rt = float(rr.headers['X-RateLimit-Reset']) - time.time()
                    rt += 5

                    # cap it at one hour
                    if rt > (60 * 60):
                        rt = (60 * 65)

                    logging.warning('{}'.format(jdata.get('message')))
                    logging.warning('sleeping {}s due to rate limiting'.format(rt))
                    time.sleep(rt)

        logging.debug('{} {}'.format(_url, rr.status_code))

        if rr.status_code == 304:
            data = None
        else:
            data = rr.json()
            # don't forget to set your tokens kids.
            if isinstance(data, dict):
                if data.get('message', '').lower() == 'bad credentials':
                    import epdb; epdb.st()

        # don't forget to set your tokens kids.
        #if isinstance(data, dict):
        #    if data.get('message', '').lower() == 'bad credentials':
        #        import epdb; epdb.st()

        fetched = []
        if 'Link' in rr.headers and follow:
            links = GHCrawler.cleanlinks(rr.headers['Link'])
            while 'next' in links:
                logging.debug(links['next'])
                if links['next'] == _url:
                    break
                #import epdb; epdb.st()
                if links['next'] in fetched:
                    import epdb; epdb.st()
                    break
                else:
                    nrr, ndata = self._geturl(links['next'], parent_url=_url, conditional=conditional, follow=False)
                    fetched.append(links['next'])
                    if ndata:
                        data += ndata
                    if 'Link' in nrr.headers:
                        links = GHCrawler.cleanlinks(nrr.headers['Link'])
                    else:
                        links = {}

        new_headers = dict(rr.headers)
        new_headers['url'] = _url
        new_headers['parent_url'] = parent_url
        new_headers['Authorizaton'] = headers['Authorization']

        # store only if changed
        if new_headers != self.headermap.get(_url):
            res = self.db.headers.replace_one(
                {'url': _url},
                new_headers,
                True
            )
            logging.debug(res)

        # always update the map
        self.headermap[_url] = new_headers

        #import epdb; epdb.st()
        return (rr, data)

    def fetch_issues(self, repo_path, number=None, force=False, phase=None):

        if not number:
            # precache the headers to reduce calls to the database
            self.headermap = {}
            headerpipe = [
                {'$project': {'_id': 0}}
            ]
            cursor = self.db.headers.aggregate(headerpipe)
            headers = list(cursor)
            for header in headers:
                self.headermap[header['url']] = header

        if not phase or phase == 'summaries':
            self.update_summaries(repo_path, number=number)
        if not phase or phase == 'issues':
            self.update_issues(repo_path, number=number)
        if not phase or phase == 'comments':
            self.update_comments(repo_path, number=number)
        if not phase or phase == 'events':
            self.update_events(repo_path, number=number)
        if not phase or phase == 'timeline':
            self.update_timeline(repo_path, number=number)
        if not phase or phase == 'files':
            self.update_files(repo_path, number=number)
        if not phase or phase == 'indexes':
            self.update_indexes(repo_path, number=number, force=force)

    def get_states(self, datatype, repo_path):
        # what state is it in mongo?
        repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
        if datatype == 'issues':
            pipeline = [
                {'$match': {'repository_url': repository_url}},
                {'$project': {'_id':0, 'number': 1, 'state': 1, 'updated_at': 1}}
            ]
        else:
            # 'url': 'https://api.github.com/repos/jctanner/issuetests/pulls/41',
            pipeline = [
                {'$match': {'url': {'$regex': '^{}/'.format(repository_url)}}},
                {'$project': {'_id':0, 'number': 1, 'state': 1, 'updated_at': 1}}
            ]

        collection = getattr(self.db, '{}'.format(datatype))

        #pprint(pipeline)
        #pprint(collection)

        cursor = collection.aggregate(pipeline)
        states = {}
        for x in list(cursor):
            number = str(x['number'])
            states[number] = x

        #if datatype == 'pullrequests':
        #    import epdb; epdb.st()

        return states

    def update_comments(self, repo_path, number=None):
        repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
        #astates = self.get_states('issues', repo_path)

        count_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'issue_url': 1}},
            {
                '$group': {
                    '_id': '$issue_url',
                    'count': {'$sum': 1}
                }
            }
        ]
        if number:
            regex = count_pipeline[0]['$match']['issue_url']['$regex']
            regex += 'issues/{}$'.format(number)
            count_pipeline[0]['$match']['issue_url']['$regex'] = regex
            #import epdb; epdb.st()
        cursor = self.db.comments.aggregate(count_pipeline)
        res = list(cursor)
        counts = {}
        for x in res:
            counts[x['_id']] = x['count']

        id_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'id': 1}},
        ]
        if number:
            regex = id_pipeline[0]['$match']['issue_url']['$regex']
            regex += 'issues/{}$'.format(number)
            id_pipeline[0]['$match']['issue_url']['$regex'] = regex
        cursor = self.db.comments.aggregate(id_pipeline)
        res = list(cursor)
        known_ids = []
        for x in res:
            known_ids.append(x['id'])
        #import epdb; epdb.st()

        pipeline = [
            {'$match': {'repository_url': repository_url}},
            {'$project': {'number': 1, 'comments': 1, 'comments_url': 1, 'url': 1, 'updated_at': 1}}
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            pipeline[0]['$match'] = match

        missing = []
        changed = []
        removed = []

        cursor = self.db.issues.aggregate(pipeline)
        issues = list(cursor)
        issues = sorted(issues, key=itemgetter('number'))

        for x in issues:
            url = x['url']
            number = str(x['number'])
            #updated_at = x['updated_at']
            comment_count = x['comments']
            #astate = astates[number]

            # new comments
            if counts.get(url, 0) < comment_count:
                logging.debug('{} expecting {} but found {}'.format(number, comment_count, counts.get(url)))

                logging.debug('force fetch comments for {}'.format(x['url']))
                rr,comments = self._geturl(x['comments_url'], conditional=False)

                #if not comments:
                #    import epdb; epdb.st()
                for cx in comments:
                    if cx['id'] not in known_ids:
                        missing.append(cx)

                if len(comments) < counts.get(url, 0):
                    import epdb; epdb.st()

                #if len(comments) < counts.get(url, 0):
                #    import epdb; epdb.st()
                #import epdb; epdb.st()

            # deleted comments
            elif counts.get(url, 0) > comment_count:
                # get the existing comment ids first
                this_pipeline = [
                    {'$match': {'issue_url': url}},
                    {'$project': {'issue_url': 1, 'id':1}}
                ]
                cursor = self.db.comments.aggregate(this_pipeline)
                res = list(cursor)
                current_database_ids = [comment['id'] for comment in res]
                rr, comments = self._geturl(x['comments_url'], conditional=False)
                current_api_ids = [comment['id'] for comment in comments]
                #import epdb; epdb.st()

                if comment_count == 0:
                    to_delete = current_database_ids
                else:
                    to_delete = []
                    for comment_id in current_database_ids:
                        if comment_id not in current_api_ids:
                            to_delete.append(comment_id)

                if to_delete:
                    removed += to_delete

            # changed comments
            elif counts.get(url) and comment_count:

                # FIXME - how do we avoid fetching the api when unnecessary?
                if counts.get(url) == comment_count:
                    continue

                # get the list of timestamps on current comments
                this_pipeline = [
                    {'$match': {'issue_url': url}},
                    {'$project': {'issue_url': 1, 'id':1, 'updated_at': 1}}
                ]
                cursor = self.db.comments.aggregate(this_pipeline)
                res = list(cursor)
                timestamps = {}
                for comment in res:
                    timestamps[comment['id']] = comment['updated_at']
                #latest = sorted(set(timestamps.values()))[-1]
                rr, comments = self._geturl(x['comments_url'])

                if not comments:
                    continue

                for comment in comments:
                    db_time = timestamps[comment['id']]
                    this_time = comment['updated_at']
                    if db_time != this_time:
                        changed.append(comment)

            if len(missing) > 50:
                logging.debug('{} new comments for {}'.format(len(missing), repo_path))
                self.db.comments.insert_many(missing)
                missing = []

            if len(changed) > 50:
                logging.debug('{} comments changed for {}'.format(len(changed), repo_path))
                for comment in changed:
                    self.db.comments.replace_one({'issue_url': url, 'id': comment['id']}, comment)
                changed = []

            if len(removed) > 50:
                logging.debug('{} comments to remove for {}'.format(len(removed), repo_path))
                res = self.db.comments.remove({'id': {'$in': removed}})
                removed = []

        if missing:
            logging.debug('{} new comments for {}'.format(len(missing), repo_path))
            self.db.comments.insert_many(missing)

        if changed:
            logging.debug('{} comments changed for {}'.format(len(changed), repo_path))
            for comment in changed:
                self.db.comments.replace_one({'issue_url': url, 'id': comment['id']}, comment)
            #import epdb; epdb.st()

        if removed:
            logging.debug('{} comments to remove for {}'.format(len(removed), repo_path))
            res = self.db.comments.remove({'id': {'$in': removed}})

        if not missing and not changed and not removed:
            logging.debug('No comment changes for {}'.format(repo_path))

    def update_events(self, repo_path, number=None):
        repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
        #astates = self.get_states('issues', repo_path)

        count_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'issue_url': 1}},
            {
                '$group': {
                    '_id': '$issue_url',
                    'count': {'$sum': 1}
                }
            }
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            count_pipeline[0]['$match'] = match
        cursor = self.db.events.aggregate(count_pipeline)
        res = list(cursor)
        counts = {}
        for x in res:
            counts[x['_id']] = x['count']

        id_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'id': 1}},
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            id_pipeline[0]['$match'] = match
        cursor = self.db.events.aggregate(id_pipeline)
        res = list(cursor)
        known_ids = []
        for x in res:
            known_ids.append(x['id'])

        '''
        pipeline = [
            {'$match': {'repository_url': repository_url}},
            {'$project': {'number': 1, 'events_url': 1, 'url': 1, 'updated_at': 1}}
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            pipeline[0]['$match']= match

        cursor = self.db.issues.aggregate(pipeline)
        issues = list(cursor)
        issues = sorted(issues, key=itemgetter('number'))
        '''

        if not number:
            pipeline = [
                {'$match': {'repository_url': repository_url}},
                {'$project': {'number': 1, 'events_url': 1, 'url': 1, 'updated_at': 1}}
            ]
            cursor = self.db.issues.aggregate(pipeline)
            issues = list(cursor)
            issues = sorted(issues, key=itemgetter('number'))
        else:
            url = '{}/issues/{}'.format(repository_url, number)
            issues = [self.db.issues.find_one({'url': url})]

        missing = []
        #changed = []
        #removed = []

        for idx,x in enumerate(issues):

            url = x['url']
            number = str(x['number'])
            #updated_at = x['updated_at']
            #comment_count = x['comments']
            #astate = astates[number]

            if not counts.get(url):
                #import epdb; epdb.st()
                rr, events = self._geturl(x['events_url'], conditional=False)
                if events:
                    for ide, event in enumerate(events):
                        events[ide]['issue_url'] = url
                    missing += events

            else:

                '''
                this_pipeline = [
                    {'$match': {'issue_url': url}},
                    {'$project': {'issue_url': 1, 'id':1, 'created_at':1}}
                ]
                cursor = self.db.events.aggregate(this_pipeline)
                res = list(cursor)
                timestamps = sorted([event['created_at'] for event in res])
                latest = timestamps[-1]
                '''

                continue
                import epdb; epdb.st()

                rr, events = self._geturl(x['events_url'], conditional=True)
                if events:
                    for ide, event in enumerate(events):
                        if event['id'] not in known_ids:
                            event['issue_url'] = url
                            missing.append(event)
                #else:
                #    import epdb; epdb.st()

            # checkpoint
            if len(missing) > 50:
                logging.debug('{} new events for {}'.format(len(missing), repo_path))
                self.db.events.insert_many(missing)
                missing = []

        if missing:
            logging.debug('{} new events for {}'.format(len(missing), repo_path))
            self.db.events.insert_many(missing)

        if not missing:
            logging.debug('No event changes for {}'.format(repo_path))

    def update_timeline(self, repo_path, number=None):
        repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
        #astates = self.get_states('issues', repo_path)

        # map out how many per issue
        count_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'issue_url': 1}},
            {
                '$group': {
                    '_id': '$issue_url',
                    'count': {'$sum': 1}
                }
            }
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            count_pipeline[0]['$match'] = match
        cursor = self.db.timeline.aggregate(count_pipeline)
        res = list(cursor)
        counts = {}
        for x in res:
            counts[x['_id']] = x['count']

        id_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'id': 1}},
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            id_pipeline[0]['$match'] = match

        cursor = self.db.timeline.aggregate(id_pipeline)
        res = list(cursor)
        known_ids = []
        for x in res:
            known_ids.append(x.get('id'))

        # get the numbers
        if number:
            url = '{}/issues/{}'.format(repository_url, number)
            issues = [self.db.issues.find_one({'url': url})]
        else:
            pipeline = [
                {'$match': {'repository_url': repository_url}},
                {'$project': {'number': 1, 'updated_at': 1}}
            ]
            cursor = self.db.issues.aggregate(pipeline)
            issues = list(cursor)
            issues = sorted(issues, key=itemgetter('number'), reverse=True)

        # fetch and figure out what is missing
        missing = []
        for issue in issues:
            issue_url = '{}/issues/{}'.format(repository_url, issue['number'])

            # get the timeline
            timeline_url = '{}/issues/{}/timeline'.format(repository_url, issue['number'])
            rr, timeline = self._geturl(timeline_url, conditional=True)

            if timeline is None:
                continue

            for idx,x in enumerate(timeline[:]):
                if 'issue_url' not in x:
                    x['issue_url'] = issue_url

                # create synthetic id for those that have none
                thisid = x.get('id')
                if not thisid:
                    thisid = hashlib.sha256(str(x).encode('utf-8')).hexdigest()
                    x['id'] = thisid

                if thisid not in known_ids:
                    missing.append(x)
                    continue

            if len(missing) > 50:
                logging.debug('checkpoint {} new timeline events for {}'.format(len(missing), repo_path))
                try:
                    self.db.timeline.insert_many(missing)
                except BulkWriteError as e:
                    #import epdb; epdb.st()
                    logging.error(e)
                missing = []

        if missing:
            logging.debug('{} new timeline events for {}'.format(len(missing), repo_path))
            try:
                self.db.timeline.insert_many(missing)
            except BulkWriteError as e:
                #import epdb; epdb.st()
                logging.error(e)
            missing = []

        '''
        count_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'issue_url': 1}},
            {
                '$group': {
                    '_id': '$issue_url',
                    'count': { '$sum': 1}
                }
            }
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            count_pipeline[0]['$match']= match
        cursor = self.db.events.aggregate(count_pipeline)
        res = list(cursor)
        counts = {}
        for x in res:
            counts[x['_id']] = x['count']

        id_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'id': 1}},
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            id_pipeline[0]['$match']= match
        cursor = self.db.events.aggregate(id_pipeline)
        res = list(cursor)
        known_ids = []
        for x in res:
            known_ids.append(x['id'])

        if not number:
            pipeline = [
                {'$match': {'repository_url': repository_url}},
                {'$project': {'number': 1, 'events_url': 1, 'url': 1, 'updated_at': 1}}
            ]
            cursor = self.db.issues.aggregate(pipeline)
            issues = list(cursor)
            issues = sorted(issues, key=itemgetter('number'))
        else:
            url = '{}/issues/{}'.format(repository_url, number)
            issues = [self.db.issues.find_one({'url': url})]

        missing = []
        changed = []
        removed = []

        for idx,x in enumerate(issues):

            url = x['url']
            number = str(x['number'])
            updated_at = x['updated_at']
            #comment_count = x['comments']
            astate = astates[number]

            if not counts.get(url):
                #import epdb; epdb.st()
                rr, events = self._geturl(x['events_url'], conditional=False)
                if events:
                    for ide, event in enumerate(events):
                        events[ide]['issue_url'] = url
                    missing += events

            else:
                continue

                rr, events = self._geturl(x['events_url'], conditional=True)
                if events:
                    for ide, event in enumerate(events):
                        if event['id'] not in known_ids:
                            event['issue_url'] = url
                            missing.append(event)

            # checkpoint
            if len(missing) > 50:
                logging.debug('{} new events for {}'.format(len(missing), repo_path))
                self.db.events.insert_many(missing)
                missing = []

        if missing:
            logging.debug('{} new events for {}'.format(len(missing), repo_path))
            self.db.events.insert_many(missing)

        if not missing:
            logging.debug('No event changes for {}'.format(repo_path))
        '''

    def update_files(self, repo_path, number=None):
        repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
        #astates = self.get_states('issues', repo_path)

        count_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'issue_url': 1}},
            {
                '$group': {
                    '_id': '$issue_url',
                    'count': {'$sum': 1}
                }
            }
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            count_pipeline[0]['$match'] = match
        cursor = self.db.pullrequest_files.aggregate(count_pipeline)
        res = list(cursor)
        counts = {}
        for x in res:
            counts[x['_id']] = x['count']

        # get a list of known shas
        sha_pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'id': 1, 'issue_url': 1, 'sha': 1}},
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            sha_pipeline[0]['$match'] = match
        cursor = self.db.pullrequest_files.aggregate(sha_pipeline)
        res = list(cursor)
        known_shas = []
        for x in res:
            known_shas.append(x['sha'])

        pipeline = [
            {'$match': {'issue_url': {'$regex': '^{}/'.format(repository_url)}}},
            {'$project': {'_id': 0, 'number': 1, 'url': 1, 'issue_url': 1}}
            #{'$match': {'repository_url': repository_url}},
            #{'$project': {'number': 1, 'events_url': 1, 'url': 1, 'updated_at': 1}}
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            pipeline[0]['$match'] = match
        missing = []
        changed = []
        #removed = []

        cursor = self.db.pullrequests.aggregate(pipeline)
        res = list(cursor)
        res = sorted(res, key=itemgetter('number'))

        #import epdb; epdb.st()

        for pull in res:
            #pnumber = pull['number']
            purl = pull['url']
            iurl = pull['issue_url']
            files_url = purl + '/files'

            rr, data = self._geturl(files_url, conditional=True)

            if data:
                for fdata in data:
                    if not isinstance(fdata, dict):
                        continue
                    fdata['pullrequest_url'] = purl
                    fdata['issue_url'] = iurl

                    if fdata['sha'] not in known_shas:
                        missing.append(fdata)
                    else:
                        changed.append(fdata)

            # checkpoint
            if len(missing) > 50:
                logging.debug('inserting {} {}'.format(len(missing), 'files'))
                self.db.pullrequest_files.insert_many(missing)
                missing = []

            # checkpoint
            if len(changed) > 50:
                logging.debug('{} {} changed'.format(len(changed), 'files'))
                for x in changed:
                    self.db.pullrequest_files.replace_one({'issue_url': x['issue_url'], 'sha': x['sha']}, x, True)
                changed = []

        if missing:
            logging.debug('inserting {} {}'.format(len(missing), 'files'))
            self.db.pullrequest_files.insert_many(missing)

        if changed:
            logging.debug('{} {} changed'.format(len(changed), 'files'))
            for x in changed:
                self.db.pullrequest_files.replace_one({'issue_url': x['issue_url'], 'sha': x['sha']}, x, True)
        #import epdb; epdb.st()

    def update_issues(self, repo_path, number=None, datatypes=['issues', 'pullrequests']):

        # mongo mod_api data
        api_states = self.get_states('issues', repo_path)
        api_states.update(self.get_states('pullrequests', repo_path))

        graph_states = self.get_summaries(repo_path, stype='issue')
        graph_states.update(self.get_summaries(repo_path, stype='issue'))
        if number:
            numbers = [number]
        else:
            numbers = sorted(set([int(x) for x in graph_states.keys()]), reverse=True)
            numbers = [x for x in range(numbers[0], numbers[-1])]

        for datatype in datatypes:

            datapath = 'issues'
            if datatype == 'pullrequests':
                datapath = 'pulls'

            collection = getattr(self.db, '{}'.format(datatype))

            # make a range of known numbers for this datatype
            repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
            number_pipe = [
                {'$match': {'url': {'$regex': '^{}/'.format(repository_url)}}},
                {'$project': {'_id': 0, 'number': 1}}
            ]
            cursor = collection.aggregate(number_pipe)
            m_numbers = sorted(set([x['number'] for x in cursor]))

            # mongo api data
            astates = self.get_states(datatype, repo_path)

            # mongo graphql data
            gstates = self.get_summaries(repo_path, stype=datatype[:-1])

            # what's missing and what has changed?
            missing = []
            changed = []
            for xnumber in numbers:

                snumber = str(xnumber)

                # fixme - github dataloss?
                if datatype == 'issues' and xnumber not in m_numbers:
                    missing.append(snumber)

                # fallback to wherever the graph stored it
                gstate = gstates.get(snumber, graph_states.get(snumber))
                if gstate:
                    # graphql shows merged when mod_api shows closed
                    if gstate['state'] == 'merged':
                        gstate['state'] = 'closed'
                else:
                    logging.debug('skipping {} -- no gstate'.format(xnumber))
                    continue

                astate = astates.get(snumber)
                if not astate:
                    try:
                        if (datatype == 'pullrequests' and gstate['type'] == 'pullrequest') or \
                              (datatype == 'issues' and gstate['type'] != 'pullrequest'):
                            logging.debug('{} {} missing'.format(datatype, snumber))
                            if snumber not in missing:
                                missing.append(snumber)
                    except Exception as e:
                        #import epdb; epdb.st()
                        logging.error(e)

                # an issue with no pullrequest
                elif not gstate and datatype == 'pullrequests':
                    continue

                # open/closed/merged
                elif gstate['state'] != astate['state']:
                    logging.debug('{} {} state change'.format(datatype, snumber))
                    if snumber not in changed:
                        changed.append(snumber)

                # graphql shows issue timestamps on PR instead of the PR timestamp
                elif gstate['updated_at'] > astate['updated_at']:
                    logging.debug('{} {} timestamp change'.format(datatype, snumber))
                    if snumber not in changed:
                        changed.append(snumber)

            # get all the things!
            to_insert = []
            to_update = []
            if missing or changed:

                tofetch = missing + changed
                tofetch = [int(x) for x in tofetch]
                tofetch = sorted(set(tofetch))
                tofetch = [str(x) for x in tofetch]
                #tofetch = sorted(set(missing + changed))

                for fnumber in tofetch:
                    url = 'https://api.github.com/repos/{}/{}/{}'.format(
                        repo_path,
                        datapath,
                        fnumber
                    )
                    logging.debug('get {}'.format(url))
                    if fnumber in missing:
                        rr,data = self._geturl(url, conditional=False)
                    else:
                        rr, data = self._geturl(url, conditional=True)

                    if not data:
                        logging.debug('{} no data'.format(fnumber))
                        continue

                    if data.get('message', '').lower() == 'not found':
                        logging.debug('{} not found'.format(fnumber))
                        continue

                    if snumber in missing:
                        to_insert.append(data)
                    else:
                        to_update.append(data)

                    # store in batches if possible
                    if len(to_insert) > 50:
                        logging.debug('inserting {} {}'.format(len(to_insert), datatype))
                        collection.insert_many(to_insert)
                        to_insert = []

                    # store in batches if possible
                    if len(to_update) > 50:
                        logging.debug('replacing {} {}'.format(len(to_update), datatype))
                        for x in to_update:
                            collection.replace_one({'url': x['url']}, x, True)
                        to_update = []

            # do all the things!
            if to_insert:
                logging.debug('inserting {} {}'.format(len(to_insert), datatype))
                collection.insert_many(to_insert)
            if to_update:
                logging.debug('replacing {} {}'.format(len(to_update), datatype))
                for x in to_update:
                    collection.replace_one({'url': x['url']}, x, True)

            if not to_insert and not to_update:
                logging.debug('No {} data to fetch for {}'.format(datatype, repo_path))

            #if datatype.startswith('pull'):
            #    import epdb; epdb.st()

    def get_summaries(self, repo_path, number=None, stype='issue'):
        collection = getattr(self.db, 'gql_{}_summaries'.format(stype))
        pipeline = [
            {'$match': {'repository.nameWithOwner': repo_path}},
            {'$project': {'_id': 0}}
        ]
        cursor = collection.aggregate(pipeline)
        issues = {}
        for issue in list(cursor):
            issues[str(issue['number'])] = issue

        return issues

    def update_summaries(self, repo_path, number=None):

        namespace = repo_path.split('/', 1)[0]
        repo = repo_path.split('/', 1)[1]

        # summaries = self.gql.get_all_summaries(namespace, repo)
        for stype in ['issue', 'pullrequest']:

            collection = getattr(self.db, 'gql_{}_summaries'.format(stype))

            if not number:
                method = getattr(self.gql, 'get_{}_summaries'.format(stype))
                summaries = method(namespace, repo)
            else:
                method = getattr(self.gql, 'get_{}_summary'.format(stype))
                summary = method(namespace, repo, number)
                if summary:
                    summaries = [summary]
                else:
                    summaries = []

            existing_issues = self.get_summaries(repo_path, stype=stype)

            missing = []
            changed = []
            for summary in enumerate(summaries):
                snumber = str(summary[1]['number'])
                data = summary[1]

                if snumber not in existing_issues:
                    missing.append(data)
                elif data != existing_issues[snumber]:
                    changed.append(data)

            if missing:
                logging.info('{} new {} in {}'.format(len(missing), stype, repo_path))
                collection.insert_many(missing)

            if changed:
                logging.info('{} changed {} in {}'.format(len(changed), stype, repo_path))
                for x in changed:
                    collection.replace_one({'url': x['url']}, x, True)

            if not missing and not changed:
                logging.info('{} summary collection in sync for {}'.format(stype, repo_path))

    def update_indexes(self, repo_path, number=None, force=False):
        #repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
        astates = self.get_states('issues', repo_path)

        if number:
            keys = [str(number)]
        else:
            keys = astates.keys()

        keys = sorted(keys, key=lambda x: int(x), reverse=True)

        for k in keys:
            v = astates.get(k)
            if not v:
                continue
            logging.debug('build index for {}'.format(v['number']))
            print(k)
            print(v)
            GithubIssueIndex(repo_path, v['number'], force=force)
            #import epdb; epdb.st()

    def close(self):
        self.client.close()


if __name__ == "__main__":

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    root.addHandler(ch)

    tokens = os.environ.get('GITHUB_TOKEN')
    if ',' in tokens:
        tokens = tokens.split(',')
    else:
        tokens = [tokens]
    ghcrawler = GHCrawler(tokens)

    #ghcrawler.fetch_issues('jctanner/issuetests', force=True)
    #ghcrawler.fetch_issues('vmware/pyvmomi', force=True)
    #ghcrawler.fetch_issues('ansible/ansible-container', force=True)
    #ghcrawler.fetch_issues('ansible/ansibullbot', force=True)
    #ghcrawler.fetch_issues('ansible/ansible-modules-extras', force=True, phase='indexes', number=2042)
    #ghcrawler.fetch_issues('ansible/ansible', phase='comments', number=16638)
    #ghcrawler.fetch_issues('ansible/ansible', phase='comments')
    #ghcrawler.fetch_issues('ansible/ansible')
    #ghcrawler.fetch_issues('ansible/ansible', phase='events', number=25181)
    #ghcrawler.fetch_issues('ansible/ansible', phase='indexes', force=True, number=23689)
    #ghcrawler.fetch_issues('ansible/ansible', phase='indexes', force=True)
    #ghcrawler.fetch_issues('ansible/ansible', phase='timeline', number=24292)
    ghcrawler.fetch_issues('ansible/ansible', phase='timeline')
    #ghcrawler.fetch_issues('ansible/ansible')
    #ghcrawler.fetch_issues('ansible/ansible', phase='indexes', force=True)

    #for i in range(1, 43):
    #    ghcrawler.fetch_issues('jctanner/issuetests', number=i)
    #ghcrawler.gql.get_issue_summary('jctanner', 'issuetests', 19)

    import epdb; epdb.st()
