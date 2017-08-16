#!/usr/bin/env python3

import logging
import re
from operator import itemgetter
from pymongo import MongoClient
from app.mod_search.queryparser import QueryParser


DBNAME = 'github_api'


class QueryExecutor(object):

    def __init__(self):
        self.qp = QueryParser()


    @staticmethod
    def merge_issue_pullrequest(issue, pullrequest):
        rdata = issue.copy()
        for k,v in pullrequest.items():
            if k not in rdata:
                rdata[k] = v
            else:
                rdata['pull_{}'.format(k)] = v
        return rdata

    def runquery(self, query):

        client = MongoClient()
        db = getattr(client, DBNAME)

        issuemap = {}

        # chop up the query into discrete parts
        querydict = self.qp.parse_to_pipeline(query)

        # start with issues
        if 'issues' in querydict['collections']:
            collection_name = 'issues'
            logging.debug('collection: {}'.format(collection_name))
            logging.debug('pipeline: {}'.format(querydict['pipeline']))
            collection = getattr(db, collection_name)
            cursor = collection.aggregate(querydict['pipeline'])
            issues = list(cursor)
            logging.debug(len(issues))

            for ix in issues:
                issuemap[ix['url']] = ix

        if 'pullrequests' in querydict['collections']:
            collection_name = 'pullrequests'
            logging.debug('collection: {}'.format(collection_name))
            logging.debug('pipeline: {}'.format(querydict['pipeline']))
            collection = getattr(db, collection_name)
            cursor = collection.aggregate(querydict['pipeline'])
            pullrequests = list(cursor)
            logging.debug(len(pullrequests))

            for px in pullrequests:
                url = px['issue_url']
                if url not in issuemap:
                    issue = db.issues.find_one({'url': url})
                    if issue:
                        #import epdb; epdb.st()
                        issuemap[url] = issue

                issuemap[url] = QueryExecutor.merge_issue_pullrequest(issuemap[url], px)

        client.close()

        # filter out non-matching labels
        if querydict['labels']:
            topop = []
            for qlabel in querydict['labels']:
                exp = re.compile(qlabel[1])
                for k,v in issuemap.items():
                    matches = [x for x in v['labels'] if exp.match(x['name'])]
                    if matches and qlabel[0] == '+':
                        pass
                    elif matches and qlabel[0] == '-':
                        topop.append(k)
                    else:
                        topop.append(k)

            for x in topop:
                issuemap.pop(x, None)

        # match on arbitrary fields
        if querydict['fields']:
            topop = []
            for qfield in querydict['fields']:
                key = qfield[0]
                exp = re.compile(qfield[1])
                for k,v in issuemap.items():

                    # cant regex on missing field
                    if key not in v:
                        topop.append(k)
                        continue

                    # cant regex on a nonetype
                    if v[key] is None:
                        topop.append(k)
                        continue

                    # safely match
                    try:
                        if not exp.match(v[key]):
                            topop.append(k)
                    except Exception as e:
                        logging.error(e)

            for x in topop:
                issuemap.pop(x, None)

        # listify the results
        results = issuemap.values()

        # sort the results now
        if querydict['sortby'] and results:
            logging.debug('sortby: {}'.format(querydict['sortby']))
            results = [x for x in results if x and querydict['sortby'][0] in x]
            try:
                if querydict['sortby'][1] == 'asc':
                    results = sorted(results, key=itemgetter(querydict['sortby'][0]), reverse=True)
                else:
                    results = sorted(results, key=itemgetter(querydict['sortby'][0]), reverse=False)
            except Exception as e:
                logging.error(e)

        return results