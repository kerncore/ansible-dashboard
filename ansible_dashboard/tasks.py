#!/usr/bin/env python3

import os
from celery import Celery
from app.crawler.ghcrawler import GHCrawler

app = Celery('tasks', broker='pyamqp://guest@localhost//', backend='rpc://')


@app.task
def add(x, y):
    return x + y

@app.task
def update_repo_issues(repo_path, issues=[]):
    tokens = os.environ.get('GITHUB_TOKEN')
    tokens = [tokens]
    ghcrawler = GHCrawler(tokens)
    if not issues:
        ghcrawler.fetch_issues(repo_path)
    else:
        for number in issues:
            ghcrawler.fetch_issues(repo_path, number=number)
    ghcrawler.close()