#!/usr/bin/env python3


from pprint import pprint
from app.mod_search.queryexecutor import QueryExecutor

queries = [
    'repo:issuetests is:open',
    'repo:issuetests is:closed',
    'repo:issuetests is:issue sort:created-asc'
    'repo:issuetests is:issue sort:created-desc'
    'repo:issuetests is:pullrequest sort:created-asc'
    'repo:issuetests is:pullrequest sort:created-desc'
]

qe = QueryExecutor()

for query in queries:
    res = qe.runquery(query)