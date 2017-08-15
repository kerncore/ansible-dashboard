#!/usr/bin/env python3

class QueryParser(object):
    def parse_to_pipeline(self, query):

        sortby = ('created_at', 'asc')
        collections = ['issues', 'pullrequests']
        matches = []
        qparts = query.split()

        for qpart in qparts:
            #print(qpart)
            value = qpart.split(':', 1)[-1]
            #print(qpart,value)

            if qpart.startswith('is:'):
                if value in ['open', 'closed', 'merged']:
                    match = {'state': value}
                    matches.append(match)
                    if value == 'merged':
                        collections = ['pullrequests']
                elif value in ['issue', 'pullrequest']:
                    if value == 'issue':
                        match = {'url': {'$regex': '.*/issues/.*'}}
                        collections = ['issues']
                    else:
                        match = {'url': {'$regex': '.*/pulls/.*'}}
                        collections = ['pullrequests']
                    matches.append(match)

            elif qpart.startswith('org:'):
                match = {'url': {'$regex': '^https://api.github.com/repos/{}/'.format(value)}}
                matches.append(match)

            elif qpart.startswith('repo:'):
                match = {'url': {'$regex': '^https://api.github.com/repos/.*/{}/'.format(value)}}
                matches.append(match)

            elif qpart.startswith('sort:'):
                key = value.split('-', 1)[0]
                if key in ['created', 'updated', 'closed', 'merged']:
                    key = key + '_at'

                direction = value.split('-', 1)[1]
                if direction != 'asc':
                    direction = 'desc'
                sortby = (key, direction)
            else:
                pass

        pipeline = []
        for match in matches:
            pipeline.append(
                {'$match': match}
            )

        return collections, pipeline, sortby



if __name__ == "__main__":
    qp = QueryParser()

    queries = [
        'repo:ansible is:issue is:open',
        'org:jctanner is:issue is:open',
        'org:jctanner is:pullrequest is:closed',
        'org:jctanner is:pullrequest is:merged'
    ]

    for query in queries:
        collections,pipeline = qp.parse_to_pipeline(query)
        print(query)
        print(collections)
        print(pipeline)