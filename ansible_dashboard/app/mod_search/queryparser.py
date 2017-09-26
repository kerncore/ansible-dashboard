#!/usr/bin/env python3


class QueryParser(object):
    def parse_to_pipeline(self, query):

        querydict = {
            'pipeline': [],
            'sortby': ('created_at', 'asc'),
            'labels': [],
            'matches': [],
            'fields': [],
            'text': [],
            'numbers': [],
            'files': [],
            'events': []
        }

        qparts = query.split()

        for qpart in qparts:

            # full text search strings
            if ':' not in qpart:
                querydict['text'].append(qpart)
                continue

            key = qpart.split(':', 1)[0]
            value = qpart.split(':', 1)[-1]

            if qpart.startswith('is:'):
                if value in ['open', 'closed']:
                    match = {'state': value}
                    querydict['matches'].append(match)
                elif value in ['merged']:
                    match = {'merged': True}
                    querydict['matches'].append(match)
                elif value in ['issue', 'pullrequest']:
                    if value == 'issue':
                        match = {'html_url': {'$regex': '.*/issues/.*'}}
                        querydict['collections'] = ['issues']
                    else:
                        match = {'html_url': {'$regex': '.*/pull/.*'}}
                    querydict['matches'].append(match)

            elif qpart.startswith('org:'):
                match = {'url': {'$regex': '^https://api.github.com/repos/{}/'.format(value)}}
                querydict['matches'].append(match)

            elif qpart.startswith('repo:'):
                match = {'url': {'$regex': '^https://api.github.com/repos/.*/{}/'.format(value)}}
                querydict['matches'].append(match)

            elif qpart.startswith('sort:'):
                key = value.split('-', 1)[0]
                if key in ['created', 'updated', 'closed', 'merged']:
                    key = key + '_at'

                direction = value.split('-', 1)[1]
                if direction != 'asc':
                    direction = 'desc'
                querydict['sortby'] = (key, direction)

            elif qpart.startswith('label:') or qpart.startswith('-label:'):
                if qpart.startswith('label:'):
                    querydict['labels'].append(('+', value))
                else:
                    querydict['labels'].append(('-', value))

            elif key == 'number':
                querydict['numbers'].append(int(value))

            elif key == 'file' or key == 'component':
                querydict['files'].append(value)

            elif key in ['bzcount', 'bugzillas_count']:

                (op, value) = self.parse_operator_from_value(value)
                querydict['matches'].append({'bugzillas_count': {op: int(value)}})

            elif key in ['sfdccount', 'sfdc_count']:

                (op, value) = self.parse_operator_from_value(value)
                querydict['matches'].append({'sfdc_count': {op: int(value)}})

            elif key in ['refcount', 'ref_count', 'reference_count', 'cross_references_count']:

                (op, value) = self.parse_operator_from_value(value)
                querydict['matches'].append({'cross_references_count': {op: int(value)}})

            elif key == 'template_data':
                # spaces here are annoying
                parts = value.rsplit(':', 1)
                parts = [x.replace('_', ' ') for x in parts]
                thiskey = '.'.join([key] + parts[:-1])
                match = {thiskey: {'$regex': parts[-1]}}
                querydict['matches'].append(match)

            else:
                # catchall
                querydict['fields'].append((key, value))

        #pipeline = []
        for match in querydict['matches']:
            querydict['pipeline'].append(
                {'$match': match}
            )
        querydict['pipeline'].append({'$project': {'_id': 0}})

        #import epdb; epdb.st()
        return querydict

    def parse_operator_from_value(self, value):

        op = '$eq'

        if value.isdigit():
            op = '$eq'

        elif value.startswith('>='):
            value = value.replace('>=', '')
            op = '$gte'

        elif value.startswith('<='):
            value = value.replace('<=', '')
            op = '$lte'

        elif value.startswith('>'):
            value = value.replace('>', '')
            op = '$gt'

        elif value.startswith('<'):
            value = value.replace('<', '')
            op = '$lt'

        return(op, value)


if __name__ == "__main__":
    qp = QueryParser()

    queries = [
        #'repo:ansible is:issue is:open',
        #'org:jctanner is:issue is:open',
        #'org:jctanner is:pullrequest is:closed',
        'org:jctanner is:pullrequest is:merged'
    ]

    for query in queries:
        querydict = qp.parse_to_pipeline(query)
        print(querydict)
