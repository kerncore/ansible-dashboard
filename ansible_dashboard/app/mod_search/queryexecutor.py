#!/usr/bin/env python3

import logging
import re
from operator import itemgetter
from pprint import pprint
from pymongo import MongoClient
from app.mod_search.queryparser import QueryParser


DBNAME = 'github_api'
INDEX_DBNAME = 'github_indexes'
INDEX_COLLECTION = 'issues'


class QueryExecutor(object):

    def __init__(self):
        self.qp = QueryParser()

    def runquery(self, query):
        querydict = self.qp.parse_to_pipeline(query)
        pprint(querydict)

        client = MongoClient()
        db = getattr(client, INDEX_DBNAME)
        collection = getattr(db, INDEX_COLLECTION)

        issuemap = {}
        cursor = collection.aggregate(querydict['pipeline'])
        issues = list(cursor)
        client.close()

        logging.debug('{} total results'.format(len(issues)))
        for i in issues:
            issuemap[i['url']] = i

        # listify the results
        results = issuemap.values()

        # sort the results now
        if querydict['sortby'] and results:
            logging.debug('sorting issues')
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


class QueryExecutorOLD(object):

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
            logging.debug('aggregating issues')
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
            logging.debug('aggregating pullrequests')
            cursor = collection.aggregate(querydict['pipeline'])
            pullrequests = list(cursor)
            logging.debug(len(pullrequests))

            for px in pullrequests:
                url = px['issue_url']
                if url not in issuemap:
                    logging.debug('find the issue')
                    issue = db.issues.find_one({'url': url})
                    if issue:
                        issuemap[url] = issue

                logging.debug('merging issue and PR data')
                issuemap[url] = QueryExecutor.merge_issue_pullrequest(issuemap[url], px)

        # get rid of anything without matching files
        if querydict.get('files'):
            logging.debug('searching for files')
            for filen in querydict['files']:
                fpipe = [
                    {'$match': {'filename': {'$regex': filen}}},
                    {'$project': {'_id': 0, 'issue_url': 1}}
                ]
                cursor = db.pullrequest_files.aggregate(fpipe)
                fmatches = list(cursor)
                fmatch_urls = [x['issue_url'] for x in fmatches]

                topop = []
                for key in issuemap.keys():
                    if key not in fmatch_urls:
                        topop.append(key)

                logging.debug('filematch removes {}'.format(len(topop)))
                for x in topop:
                    issuemap.pop(x, None)

        client.close()

        # filter specific numbers
        if querydict['numbers']:
            logging.debug('filtering on numbers')
            topop = []
            for k,v in issuemap.items():
                if v['number'] not in querydict['numbers']:
                    topop.append(k)

            logging.debug('numbers removes {}'.format(len(topop)))
            for x in topop:
                issuemap.pop(x, None)

        # filter out non-matching labels
        if querydict['labels']:
            logging.debug('filtering on labels')
            topop = []
            for qlabel in querydict['labels']:
                exp = re.compile(qlabel[1])
                for k,v in issuemap.items():
                    matches = [x for x in v['labels'] if exp.match(x['name'])]

                    # FIXME - this is ugly
                    if matches and qlabel[0] == '+':
                        pass
                    elif matches and qlabel[0] == '-':
                        if 'feature_pull_request' not in [x['name'] for x in v['labels']]:
                            import epdb; epdb.st()
                        topop.append(k)
                    elif qlabel[0] == '-' and not v['labels']:
                        pass
                    elif qlabel[0] == '+' and not matches:
                        #if qlabel[0] == '-':
                        #    if 'feature_pull_request' not in [x['name'] for x in v['labels']]:
                        #        import epdb; epdb.st()
                        topop.append(k)

            logging.debug('labels removes {}'.format(len(topop)))
            for x in topop:
                issuemap.pop(x, None)

        # match on arbitrary fields
        if querydict['fields']:
            logging.debug('filtering on fields')
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

                    # some fields are dicts such as "user"
                    val = v[key]
                    if isinstance(val, dict):
                        if 'login' in val:
                            val = val['login']
                        elif 'name' in val:
                            val = va['name']

                    # safely match
                    try:
                        if not exp.match(val):
                            topop.append(k)
                    except Exception as e:
                        logging.error(e)

            logging.debug('fields removes {}'.format(len(topop)))
            for x in topop:
                issuemap.pop(x, None)

        # listify the results
        results = issuemap.values()

        # sort the results now
        if querydict['sortby'] and results:
            logging.debug('sorting issues')
            logging.debug('sortby: {}'.format(querydict['sortby']))
            results = [x for x in results if x and querydict['sortby'][0] in x]
            try:
                if querydict['sortby'][1] == 'asc':
                    results = sorted(results, key=itemgetter(querydict['sortby'][0]), reverse=True)
                else:
                    results = sorted(results, key=itemgetter(querydict['sortby'][0]), reverse=False)
            except Exception as e:
                logging.error(e)

        logging.debug('total: {}'.format(len(results)))
        #pprint([x['number'] for x in results])
        return results



if __name__ == "__main__":
    queries = [
        'repo:ansible is:issue is:open',
        'org:jctanner is:issue is:open',
        'org:jctanner is:pullrequest is:closed',
        'org:jctanner is:pullrequest is:merged'
    ]

    qe = QueryExecutor()

    for query in queries:
        pprint(query)
        res = qe.runquery(query)
        print(len(res))
        pprint([x['url'] for x in res])
        #import epdb; epdb.st()