#!/usr/bin/env python3

import logging
import re
import sys
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

        logging.debug('{} total pipeline matches'.format(len(issues)))
        for i in issues:
            issuemap[i['url']] = i

        # filter on labels
        if querydict.get('labels'):
            to_remove = []
            for k,v in issuemap.items():

                ilabels = [x['name'] for x in v['labels']]

                for ltup in querydict['labels']:
                    if ltup[0] == '+' and ltup[1] not in ilabels:
                        to_remove.append(k)
                    if ltup[0] == '-' and ltup[1] in ilabels:
                        to_remove.append(k)

            to_remove = sorted(set(to_remove))
            for tr in to_remove:
                issuemap.pop(tr, None)

        # filter on files
        if querydict.get('files'):
            logging.debug('searching for files')
            for filen in querydict['files']:
                matcher = re.compile(filen)
                topop = []
                for k,v in issuemap.items():

                    if not v.get('files'):
                        topop.append(k)
                        continue

                    found = False
                    for filen in v['files']:
                        if matcher.match(filen):
                            found = True
                            break

                    if not found:
                        topop.append(k)

                logging.debug('filematch removes {}'.format(len(topop)))
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

        return results


if __name__ == "__main__":

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    root.addHandler(ch)

    queries = [
        #'repo:ansible is:issue is:open',
        #'org:jctanner is:issue is:open',
        #'org:jctanner is:pullrequest is:closed',
        #'org:jctanner is:pullrequest is:merged',
        #'file:.*cloud.*',
        #'org:ansible repo:ansible bzcount:>0'
        #'repo:ansible is:open template_data:ansible_version:.*2.3.*',
        #'repo:ansible is:open -label:affects_2.4 template_data:ansible_version:.*2.4.*'
        'sfdc_count:>=3 sort:sfdc_count-asc'
    ]

    qe = QueryExecutor()

    for query in queries:
        pprint(query)
        res = qe.runquery(query)
        print(len(res))
        pprint([x['html_url'] for x in res])
        #import epdb; epdb.st()
