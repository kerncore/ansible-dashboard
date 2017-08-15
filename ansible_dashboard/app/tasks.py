#!/usr/bin/env python3

import os
import logging
from celery import Celery
from app.mod_tokens.models import Token
from app.crawler.ghcrawler import GHCrawler

capp = Celery('tasks', broker='pyamqp://guest@localhost//', backend='rpc://')


@capp.task
def add(x, y):
    return x + y

@capp.task
def update_github_repo_issues(repo_path, issues=[]):
    #tokens = os.environ.get('GITHUB_TOKEN')
    #tokens = [tokens]

    '''
    parts = repo_path.split('/')
    logging.debug(parts)
    user = parts[0]
    repo = parts[1]
    '''

    tokens = Token.query.all()
    ctokens = [x.token for x in tokens]
    logging.info(ctokens)

    ghcrawler = GHCrawler(ctokens)
    if not issues:
        logging.info('fetching all issues for {}'.format(repo_path))
        ghcrawler.fetch_issues(repo_path)
    else:
        logging.info('fetching {} issues for {}'.format(len(issues), repo_path))
        for number in issues:
            ghcrawler.fetch_issues(repo_path, number=number)
    ghcrawler.close()