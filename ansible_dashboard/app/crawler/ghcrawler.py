#!/usr/bin/env ptyhon3

import logging
import os
import requests
import sys
from pymongo import MongoClient
from ghgraphql import GithubGraphQLClient

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

    def _geturl(self, url):
        headers = {'Authorization': 'token {}'.format(self.tokens[0])}
        rr = requests.get(url, headers=headers)
        data = rr.json()

        # don't forget to set your tokens kids.
        if data.get('message', '').lower() == 'bad credentials':
            import epdb; epdb.st()

        return data

    def fetch_issues(self, repo_path):
        self.update_summaries(repo_path)
        self.update_data(repo_path)

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

        return states

    def update_data(self, repo_path, datatypes=['issues', 'pullrequests']):

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
            for number,gstate in gstates.items():
                astate = astates.get(number)
                if not astate:
                    missing.append(number)

                # graphql shows merged when api shows closed
                if gstate['state'] == 'merged':
                    gstate['state'] = 'closed'

                # open/closed/merged
                elif gstate['state'] != astate['state']:
                    #import epdb; epdb.st()
                    changed.append(number)

                # graphql shows issue timestamps on PR instead of the PR timestamp
                elif gstate['updated_at'] > astate['updated_at']:
                    changed.append(number)

            # get all the things!
            to_insert = []
            to_update = []
            if missing or changed:
                tofetch = sorted(set(missing + changed))
                for number in tofetch:
                    url = 'https://api.github.com/repos/{}/{}/{}'.format(
                        repo_path,
                        datapath,
                        number
                    )
                    logging.debug('get {}'.format(url))
                    data = self._geturl(url)

                    if number in ["31", 31]:
                        import epdb; epdb.st()

                    if data.get('message', '').lower() == 'not found':
                        continue

                    if number in missing:
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
                    collection.replace_one({'url': x['url']}, x)

    def get_summaries(self, repo_path, stype='issue'):
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

    def update_summaries(self, repo_path):

        namespace = repo_path.split('/', 1)[0]
        repo = repo_path.split('/', 1)[1]

        # summaries = self.gql.get_all_summaries(namespace, repo)
        for stype in ['issue', 'pullrequest']:

            collection = getattr(self.db, 'gql_{}_summaries'.format(stype))
            method = getattr(self.gql, 'get_{}_summaries'.format(stype))
            summaries = method(namespace, repo)

            #if stype == 'pullrequest':
            #    import epdb; epdb.st()

            existing_issues = self.get_summaries(repo_path, stype=stype)

            missing = []
            changed = []
            for summary in enumerate(summaries):
                number = str(summary[1]['number'])
                data = summary[1]

                if number not in existing_issues:
                    missing.append(data)
                elif data != existing_issues[number]:
                    changed.append(data)

                #if number == "31":
                #    import epdb; epdb.st()

            if missing:
                logging.info('{} new {} in {}'.format(len(missing), stype, repo_path))
                collection.insert_many(missing)

            if changed:
                logging.info('{} changed {} in {}'.format(len(changed), stype, repo_path))
                for x in changed:
                    collection.replace_one({'url': x['url']}, x)

            if not missing and not changed:
                logging.info('{} summary collection in sync for {}'.format(stype, repo_path))


if __name__ == "__main__":
    tokens = os.environ.get('GITHUB_TOKEN')
    tokens = [tokens]
    ghcrawler = GHCrawler(tokens)
    ghcrawler.fetch_issues('jctanner/issuetests')
