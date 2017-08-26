#!/usr/bin/env python

# https://raw.githubusercontent.com/ansible/ansibullbot/master/ansibullbot/utils/gh_gql_client.py
# https://developer.github.com/v4/explorer/
# https://developer.github.com/v4/guides/forming-calls/

import jinja2
import json
import logging
import requests
import time
import timeout_decorator
from operator import itemgetter


QUERY_FIELDS = """
id
url
number
state
createdAt
updatedAt
labels(first: 100) {
    edges {
        node {
            name
        }
    }
}
repository {
    nameWithOwner
}
"""

QUERY_TEMPLATE = """
{
    repository(owner:"{{ OWNER }}", name:"{{ REPO }}") {
        {{ OBJECT_TYPE }}({{ OBJECT_PARAMS }}) {
            pageInfo {
                startCursor
                endCursor
                hasNextPage
                hasPreviousPage
            }
            edges {
                node {
                {{ FIELDS }}
                }
            }
        }
    }
}
"""

QUERY_TEMPLATE_SINGLE_NODE = """
{
    repository(owner:"{{ OWNER }}", name:"{{ REPO }}") {
          {{ OBJECT_TYPE }}({{ OBJECT_PARAMS }}){
            {{ FIELDS }}
        }
    }
}
"""

class GithubGraphQLClient(object):
    baseurl = 'https://api.github.com/graphql'

    def __init__(self, token):
        self.token = token
        self.headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer %s' % self.token,
        }
        self.environment = jinja2.Environment()

    @timeout_decorator.timeout(5)
    def call_requests(self, url, headers, data):
        return requests.post(url, headers=headers, data=data)

    '''
    def get_issue_summaries(self, repo_url, baseurl=None, cachefile=None):
        """Return a dict of all issue summaries with numbers as keys

        Adds a compatibility method for the webscraper

        Args:
            repo_url  (str): username/repository
            baseurl   (str): not used
            cachefile (str): not used
        """
        owner = repo_url.split('/', 1)[0]
        repo = repo_url.split('/', 1)[1]
        summaries = self.get_all_summaries(owner, repo)

        issues = {}
        for x in summaries:
            issues[str(x['number'])] = x
        return issues
    '''

    def get_last_number(self, repo_path):
        """Return the very last issue/pr number opened for a repo

        Args:
            owner (str): the github namespace
            repo  (str): the github repository
        """
        owner = repo_path.split('/', 1)[0]
        repo = repo_path.split('/', 1)[1]

        isummaries = self.get_summaries(owner, repo, otype='issues',
                                        last='last: 1', first=None, states=None,
                                        paginate=False)
        psummaries = self.get_summaries(owner, repo, otype='pullRequests',
                                        last='last: 1', first=None, states=None,
                                        paginate=False)

        if isummaries[-1]['number'] > psummaries[-1]['number']:
            return isummaries[-1]['number']
        else:
            return psummaries[-1]['number']

    def get_all_summaries(self, owner, repo, states=[]):
        """Collect all the summary data for issues and pullreuests

        Args:
            owner (str): the github namespace
            repo  (str): the github repository
        """

        isummaries = self.get_issue_summaries(owner, repo, otype='pullRequests', states=states)
        psummaries = self.get_pullrequest_summaries(owner, repo, otype='pullRequests', states=states)
        return(isummaries, psummaries)

    def get_issue_summaries(self, owner, repo, states=[]):
        isummaries = self.get_summaries(owner, repo, otype='issues', states=states)
        isummaries = sorted(isummaries, key=itemgetter('number'))
        return isummaries

    def get_issue_summary(self, owner, repo, number, states=[]):
        isummary = self.get_summary(owner + '/' + repo, 'issue', number)
        return isummary

    def get_pullrequest_summaries(self, owner, repo, states=[]):
        psummaries = self.get_summaries(owner, repo, otype='pullRequests', states=states)
        psummaries = sorted(psummaries, key=itemgetter('number'))
        return psummaries

    def get_pullrequest_summary(self, owner, repo, number, states=[]):
        psummary = self.get_summary(owner +'/' + repo, 'pullRequest', number)
        return psummary

    def get_summaries(self, owner, repo, otype='issues', last=None, first='first: 100', states='states: OPEN', paginate=True):
        """Collect all the summary data for issues or pullreuests

        Args:
            owner     (str): the github namespace
            repo      (str): the github repository
            otype     (str): issues or pullRequests
            first     (str): number of nodes per page, oldest to newest
            last      (str): number of nodes per page, newest to oldest
            states    (str): open or closed issues
            paginate (bool): recurse through page results

        """

        templ = self.environment.from_string(QUERY_TEMPLATE)

        # after: "$endCursor"
        after = None

        '''
        # first: 100
        first = 'first: 100'
        # states: OPEN
        states = 'states: OPEN'
        '''

        nodes = []
        pagecount = 0
        while True:
            logging.debug('%s/%s %s pagecount:%s nodecount: %s' %
                          (owner,repo, otype, pagecount, len(nodes)))

            if states:
                issueparams = ', '.join([x for x in [states, first, last, after] if x])
            else:
                issueparams = ', '.join([x for x in [first, last, after] if x])
            query = templ.render(OWNER=owner, REPO=repo, OBJECT_TYPE=otype, OBJECT_PARAMS=issueparams, FIELDS=QUERY_FIELDS)

            payload = {
                #'query': query.encode('ascii', 'ignore').strip(),
                'query': query.strip(),
                'variables': '{}',
                'operationName': None
            }

            logging.debug(self.headers)
            logging.debug(self.baseurl)
            logging.debug(payload)

            success = False
            while not success:
                try:
                    #rr = requests.post(self.baseurl, headers=self.headers, data=json.dumps(payload))
                    rr = self.call_requests(self.baseurl, self.headers, json.dumps(payload))
                    success = True
                except requests.exceptions.ConnectionError:
                    logging.warning('connection error. sleep 2m')
                    time.sleep(60*2)
                except timeout_decorator.timeout_decorator.TimeoutError:
                    logging.warning('sleeping {}s due to timeout'.format(60 * 2))
                    time.sleep(60 * 2)
                    continue

            logging.debug(rr.status_code)
            logging.debug(rr.reason)

            if not rr.ok:
                break
            data = rr.json()
            if not data:
                break

            # keep each edge/node/issue
            for edge in data['data']['repository'][otype]['edges']:
                node = edge['node']
                self.update_node(node, otype.lower()[:-1], owner, repo)
                nodes.append(node)

            if not paginate:
                break

            pageinfo = data.get('data', {}).get('repository', {}).get(otype, {}).get('pageInfo')
            if not pageinfo:
                break
            if not pageinfo.get('hasNextPage'):
                break

            after = 'after: "%s"' % pageinfo['endCursor']
            pagecount += 1

        #if otype == 'pullRequests':
        #    import epdb; epdb.st()

        return nodes

    def get_summary(self, repo_url, otype, number):
        """Collect all the summary data for issues or pull requests ids

        Args:
            repo_url  (str): repository URL
            otype     (str): issue or pullRequest
            number    (str): Identifies the pull-request or issue, for example: 12345
        """
        owner = repo_url.split('/', 1)[0]
        repo = repo_url.split('/', 1)[1]

        template = self.environment.from_string(QUERY_TEMPLATE_SINGLE_NODE)

        query = template.render(OWNER=owner, REPO=repo, OBJECT_TYPE=otype, OBJECT_PARAMS='number: %s' % number, FIELDS=QUERY_FIELDS)

        payload = {
            #'query': query.encode('ascii', 'ignore').strip(),
            'query': query.strip(),
            'variables': '{}',
            'operationName': None
        }

        logging.debug(self.headers)
        logging.debug(self.baseurl)
        logging.debug(payload)

        ''''
        rr = requests.post(self.baseurl, headers=self.headers, data=json.dumps(payload))
        logging.debug(rr.status_code)
        logging.debug(rr.reason)
        data = rr.json()
        '''

        success = False
        while not success:
            try:
                # rr = requests.post(self.baseurl, headers=self.headers, data=json.dumps(payload))
                rr = self.call_requests(self.baseurl, self.headers, json.dumps(payload))
                success = True
            except requests.exceptions.ConnectionError:
                logging.warning('connection error. sleep 2m')
                time.sleep(60 * 2)
            except timeout_decorator.timeout_decorator.TimeoutError:
                logging.warning('sleeping {}s due to timeout'.format(60 * 2))
                time.sleep(60 * 2)
                continue

        data = rr.json()

        #import epdb; epdb.st()
        try:
            node = data['data']['repository'][otype]
        except TypeError:
            # errors: message: Something went wrong while executing your query.
            return None

        if node is None:
            return

        self.update_node(node, otype, owner, repo)

        return node

    def update_node(self, node, node_type, owner, repo):
        node['state'] = node['state'].lower()
        node['created_at'] = node.get('createdAt')
        node['updated_at'] = node.get('updatedAt')

        if 'repository' not in node:
            node['repository'] = {}

        if 'nameWithOwner' not in node['repository']:
            node['repository']['nameWithOwner'] = '%s/%s' % (owner, repo)

        node['type'] = node_type


###################################
# TESTING ...
###################################
if __name__ == "__main__":
    import ansibullbot.constants as C
    logging.basicConfig(level=logging.DEBUG)
    client = GithubGraphQLClient(C.DEFAULT_GITHUB_TOKEN)
    summaries = client.get_all_summaries('ansible', 'ansible')
    ln = client.get_last_number('ansible/ansible')
    #import epdb; epdb.st()
