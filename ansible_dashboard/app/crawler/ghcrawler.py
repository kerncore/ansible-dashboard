#!/usr/bin/env ptyhon3

import logging
import os
import requests
import sys
from pymongo import MongoClient
from app.crawler.ghgraphql import GithubGraphQLClient

from pprint import pprint

root = logging.getLogger()
root.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
root.addHandler(ch)


class GHCrawler(object):

    DBNAME = 'github_api'

    def __init__(self, tokens):
        self.tokens = tokens
        self.gql = GithubGraphQLClient(self.tokens[0])
        self.client = MongoClient()
        self.db = getattr(self.client, self.DBNAME)

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

    def _geturl(self, url, since=None, conditional=True):

        if since:
            _url = url + '?since=%s' % since
        else:
            _url = url

        headers = {
            'Authorization': 'token {}'.format(self.tokens[0]),
            'User-Agent': 'Awesome Octocat-App'
        }

        # https://developer.github.com/v3/#conditional-requests
        db_headers = self.db.headers.find_one({'url': _url}) or {}
        if db_headers and conditional:
            if db_headers.get('ETag'):
                headers['If-None-Match'] = db_headers['ETag']
            else:
                headers['If-Modified-Since'] = db_headers['Date']

        rr = requests.get(_url, headers=headers)

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

        if 'Link' in rr.headers:
            links = GHCrawler.cleanlinks(rr.headers['Link'])
            while 'next' in links:
                logging.debug(links['next'])
                if links['next'] == _url:
                    break
                nrr, ndata = self._geturl(links['next'], conditional=conditional)
                if ndata:
                    data += ndata
                if 'Link' in nrr.headers:
                    links = GHCrawler.cleanlinks(nrr.headers['Link'])
                else:
                    links = {}

        new_headers = dict(rr.headers)
        new_headers['url'] = _url
        res = self.db.headers.replace_one(
            {'url': _url},
            new_headers,
            True
        )

        #import epdb; epdb.st()
        return (rr, data)

    def fetch_issues(self, repo_path, number=None):
        self.update_summaries(repo_path, number=number)
        self.update_issues(repo_path, number=number)
        self.update_comments(repo_path, number=number)
        self.update_events(repo_path, number=number)

    def get_states(self, datatype, repo_path):
        # what state is it in mongo?
        repository_url = 'https://api.github.com/repos/{}'.format(repo_path)
        if datatype == 'issues':
            pipeline = [
                {'$match': {'repository_url': repository_url}},
                {'$project': {'number': 1, 'state': 1, 'updated_at': 1}}
            ]
        else:
            # 'url': 'https://api.github.com/repos/jctanner/issuetests/pulls/41',
            pipeline = [
                {'$match': {'url': {'$regex': '^{}/'.format(repository_url)}}},
                {'$project': {'number': 1, 'state': 1, 'updated_at': 1}}
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
        repository_url = 'https://mod_api.github.com/repos/{}'.format(repo_path)
        astates = self.get_states('issues', repo_path)

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
            pipeline[0]['$match']= match

        missing = []
        changed = []
        removed = []

        cursor = self.db.issues.aggregate(pipeline)
        for x in list(cursor):
            url = x['url']
            number = str(x['number'])
            updated_at = x['updated_at']
            comment_count = x['comments']
            astate = astates[number]

            # new comments
            if counts.get(url, 0) < comment_count:
                logging.debug('{} expecting {} but found {}'.format(number, comment_count, counts.get(url)))
                rr,comments = self._geturl(x['comments_url'], conditional=False)
                #if not comments:
                #    import epdb; epdb.st()
                for cx in comments:
                    if cx['id'] not in known_ids:
                        missing.append(cx)

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

                # FIXME - how do we avoid fetching the mod_api when unnecessary?


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
                latest = sorted(set(timestamps.values()))[-1]
                #rr, comments = self._geturl(x['comments_url'], since=latest)
                rr, comments = self._geturl(x['comments_url'])

                if not comments:
                    continue

                for comment in comments:
                    db_time = timestamps[comment['id']]
                    this_time = comment['updated_at']
                    if db_time != this_time:
                        changed.append(comment)

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
        astates = self.get_states('issues', repo_path)

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

        pipeline = [
            {'$match': {'repository_url': repository_url}},
            {'$project': {'number': 1, 'events_url': 1, 'url': 1, 'updated_at': 1}}
        ]
        if number:
            match = {'issue_url': {'$regex': '^{}/issues/{}$'.format(repository_url, number)}}
            pipeline[0]['$match']= match
        missing = []
        changed = []
        removed = []

        cursor = self.db.issues.aggregate(pipeline)
        for x in list(cursor):
            url = x['url']
            number = str(x['number'])
            updated_at = x['updated_at']
            #comment_count = x['comments']
            astate = astates[number]

            #events_pipeline = [{'$match': {'issue_url': url}}]
            #cursor = self.db.comments.aggregate(events_pipeline)
            #res = list(cursor)

            if not counts.get(url):
                rr, events = self._geturl(x['events_url'], conditional=False)
                if events:
                    for ide, event in enumerate(events):
                        events[ide]['issue_url'] = url
                    missing += events

            else:
                this_pipeline = [
                    {'$match': {'issue_url': url}},
                    {'$project': {'issue_url': 1, 'id':1, 'created_at':1}}
                ]
                cursor = self.db.events.aggregate(this_pipeline)
                res = list(cursor)
                timestamps = sorted([event['created_at'] for event in res])
                latest = timestamps[-1]

                rr, events = self._geturl(x['events_url'], conditional=True)
                if events:
                    for ide, event in enumerate(events):
                        if event['id'] not in known_ids:
                            event['issue_url'] = url
                            missing.append(event)

        if missing:
            logging.debug('{} new events for {}'.format(len(missing), repo_path))
            self.db.events.insert_many(missing)

        if not missing:
            logging.debug('No event changes for {}'.format(repo_path))

    def update_issues(self, repo_path, number=None, datatypes=['issues', 'pullrequests']):

        # mongo mod_api data
        api_states = self.get_states('issues', repo_path)
        api_states.update(self.get_states('pullrequests', repo_path))

        graph_states = self.get_summaries(repo_path, stype='issue')
        graph_states.update(self.get_summaries(repo_path, stype='issue'))
        if number:
            numbers = [number]
        else:
            numbers = sorted(set([int(x) for x in graph_states.keys()]))
            numbers = [x for x in range(numbers[0], numbers[-1])]

        for datatype in datatypes:

            datapath = 'issues'
            if datatype == 'pullrequests':
                datapath = 'pulls'

            collection = getattr(self.db, '{}'.format(datatype))

            # mongo api data
            astates = self.get_states(datatype, repo_path)

            # mongo graphql data
            gstates = self.get_summaries(repo_path, stype=datatype[:-1])

            # what's missing and what has changed?
            missing = []
            changed = []
            for xnumber in numbers:
                snumber = str(xnumber)

                # fallback to wherever the graph stored it
                gstate = gstates.get(snumber, graph_states.get(snumber))
                if gstate:
                    # graphql shows merged when mod_api shows closed
                    if gstate['state'] == 'merged':
                        gstate['state'] = 'closed'
                else:
                    logging.debug('skipping {} -- no gstate'.format(number))
                    continue

                astate = astates.get(snumber)
                if not astate:
                    try:
                        if (datatype == 'pullrequests' and gstate['type'] == 'pullrequest') or \
                              (datatype == 'issues' and gstate['type'] != 'pullrequest'):
                            logging.debug('{} {} missing'.format(datatype, snumber))
                            if snumber not in missing:
                                missing.append(snumber)
                    except:
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
                tofetch = sorted(set(missing + changed))
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

    def close(self):
        self.client.close()


if __name__ == "__main__":
    tokens = os.environ.get('GITHUB_TOKEN')
    tokens = [tokens]
    ghcrawler = GHCrawler(tokens)

    #ghcrawler.fetch_issues('jctanner/issuetests')
    #ghcrawler.fetch_issues('vmware/pyvmomi')

    for i in range(1, 40):
        ghcrawler.fetch_issues('jctanner/issuetests', number=i)

    #ghcrawler.gql.get_issue_summary('jctanner', 'issuetests', 19)
