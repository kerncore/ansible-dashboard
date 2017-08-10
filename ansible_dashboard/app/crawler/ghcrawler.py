#!/usr/bin/env ptyhon3

import logging
import os
import requests
import sys
from pymongo import MongoClient
from ghgraphql import GithubGraphQLClient


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

    def fetch_issues(self, repo_path):
        self.update_summaries(repo_path)

    def update_summaries(self, repo_path):
        namespace = repo_path.split('/', 1)[0]
        repo = repo_path.split('/', 1)[1]
        summaries = self.gql.get_all_summaries(namespace, repo)

        pipeline = [
            {'$match': {'repository.nameWithOwner': repo_path}},
            {'$project': {'_id': 0}}
        ]
        cursor = self.db.gql_summaries.aggregate(pipeline)
        issues = {}
        for issue in list(cursor):
            issues[str(issue['number'])] = issue

        missing = []
        changed = []
        for summary in enumerate(summaries):
            number = str(summary[1]['number'])
            data = summary[1]

            if number not in issues:
                missing.append(data)
            elif data != issues[number]:
                import epdb; epdb.st()
                changed.append(data)

        if missing:
            logging.info('{} new issues in {}'.format(len(missing), repo_path))
            self.db.gql_summaries.insert_many(missing)

        if changed:
            logging.info('{} changed issues in {}'.format(len(changed), repo_path))
            for x in changed:
                self.db.gql_summaries.replace_one({'url': x['url']}, x)

        if not missing and not changed:
            logging.info('summary db in sync for {}'.format(repo_path))


if __name__ == "__main__":
    tokens = os.environ.get('GITHUB_TOKEN')
    tokens = [tokens]
    ghcrawler = GHCrawler(tokens)
    ghcrawler.fetch_issues('jctanner/issuetests')
