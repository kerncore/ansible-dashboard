#!/usr/bin/env python3


from pprint import pprint
from app.mod_search.queryexecutor import QueryExecutor

queries = [
    'repo:issuetests is:open',
    'repo:issuetests is:closed',
    'repo:issuetests is:issue sort:created-asc',
    'repo:issuetests is:issue sort:created-desc',
    'repo:issuetests is:pullrequest sort:created-asc',
    'repo:issuetests is:pullrequest sort:created-desc',
    'repo:issuetests is:issue sort:created-desc label:^bug label:question',
    'repo:issuetests is:issue sort:created-desc label:^bug label:question',
    'title:.*surfacing.*',
    'body:.*Traceback.*',
    'user:jctanner',
    'number:1',
    'repo:issuetests number:1',
]

queries = [
    #'file:.*vmware.*',
    'is:closed file:.*vmware.* label:^core -label:^feature'
]

qe = QueryExecutor()

for qs in queries:
    print('######################')
    print('QUERY: {}'.format(qs))
    res = qe.runquery(qs)
    #import epdb; epdb.st()