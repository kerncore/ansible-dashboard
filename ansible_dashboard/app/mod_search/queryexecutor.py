#!/usr/bin/env python3

import logging
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

        # build the pipelines
        collections,pipeline,sortby = self.qp.parse_to_pipeline(query)

        # start with issues
        if 'issues' in collections:
            collection_name = 'issues'
            logging.debug('collection: {}'.format(collection_name))
            logging.debug('pipeline: {}'.format(pipeline))
            collection = getattr(db, collection_name)
            cursor = collection.aggregate(pipeline)
            issues = list(cursor)
            logging.debug(len(issues))

            for ix in issues:
                issuemap[ix['url']] = ix

        if 'pullrequests' in collections:
            collection_name = 'pullrequests'
            logging.debug('collection: {}'.format(collection_name))
            logging.debug('pipeline: {}'.format(pipeline))
            collection = getattr(db, collection_name)
            cursor = collection.aggregate(pipeline)
            pullrequests = list(cursor)
            logging.debug(len(pullrequests))

            for px in pullrequests:
                url = px['issue_url']
                if url not in issuemap:
                    issue = db.issues.find_one({'url': url})
                    if not issue:
                        import epdb; epdb.st()
                    issuemap[url] = issue

                issuemap[url] = QueryExecutor.merge_issue_pullrequest(issuemap[url], px)
                #import epdb; epdb.st()

        '''
        for collection_name in collections:
            logging.debug('collection: {}'.format(collection_name))
            logging.debug('pipeline: {}'.format(pipeline))
            collection = getattr(db, collection_name)
            cursor = collection.aggregate(pipeline)
            res = list(cursor)
            logging.debug(len(res))
            if res:
                results += res
        '''

        client.close()
        results = issuemap.values()

        if sortby and results:
            logging.debug('sortby: {}'.format(sortby))
            results = [x for x in results if x and sortby[0] in x]
            try:
                if sortby[1] == 'asc':
                    results = sorted(results, key=itemgetter(sortby[0]), reverse=True)
                else:
                    results = sorted(results, key=itemgetter(sortby[0]), reverse=False)
            except Exception as e:
                logging.error(e)

        return results