#!/usr/bin/env python

# https://github.com/python-bugzilla/python-bugzilla/blob/master/examples/query.py
'''
bzapi = bugzilla.Bugzilla(URL)
query = bzapi.build_query(
    product="Fedora",
    component="python-bugzilla")
bugs = bzapi.query(query)
'''
'''
(Epdb) pp ticket.external_bugs
[{'bug_id': 1393547,
  'ext_bz_bug_id': '01722303',
  'ext_bz_id': 60,
  'ext_description': '[RFE] Operative system icon an operative system information does NOT match',
  'ext_priority': '3 (Normal)',
  'ext_status': 'Closed',
  'id': 303183,
  'type': {'can_get': True,
           'can_send': True,
           'description': 'Red Hat Customer Portal',
           'full_url': 'https://access.redhat.com/support/cases/%id%',
           'id': 60,
           'must_send': True,
           'send_once': True,
           'type': 'SFDC',
           'url': 'https://access.redhat.com'}}]
'''

'''
(Epdb) pp ticket.external_bugs
[{'bug_id': 1174251,
  'ext_bz_bug_id': '7635',
  'ext_bz_id': 112,
  'ext_description': 'None',
  'ext_priority': 'None',
  'ext_status': 'None',
  'id': 259253,
  'type': {'can_get': False,
           'can_send': False,
           'description': 'Foreman Issue Tracker',
           'full_url': 'http://projects.theforeman.org/issues/%id%',
           'id': 112,
           'must_send': False,
           'send_once': False,
           'type': 'None',
           'url': 'http://projects.theforeman.org/issues'}}]
'''

import logging
import os
import pickle
import pymongo
#import requests_cache
import sys
import time
from datetime import datetime
from pprint import pprint
from bugzilla.rhbugzilla import RHBugzilla
from xmlrpc.client import DateTime

#requests_cache.install_cache('.bz_cache')

bugzilla = RHBugzilla(
    url='https://bugzilla.redhat.com/xmlrpc.cgi',
    user=os.environ.get('BUGZILLA_USERNAME'),
    password=os.environ.get('BUGZILLA_PASSWORD')
)

#query = bugzilla.build_query(product='Ansible Tower')
#tickets = bugzilla.query(query)

'''
(Epdb) ticket = tickets[0]
(Epdb) pp ticket.getcomments()[0].keys()
['count',
 'author',
 'text',
 'creator',
 'creation_time',
 'bug_id',
 'creator_id',
 'time',
 'id',
 'is_private']
'''

products = [
    'Ansible Tower',
    #'Red Hat Satellite 6',
    'CloudForms Common',
    'CloudForms Cloud Engine',
    'Red Hat CloudForms Management Engine'
]

tickets = []


# https://bugzilla.redhat.com/buglist.cgi?
#	bug_status=NEW
#	bug_status=ASSIGNED
#	bug_status=POST
#	bug_status=MODIFIED
#	bug_status=ON_DEV
#	bug_status=ON_QA
#	bug_status=VERIFIED
#	bug_status=RELEASE_PENDING
#	bug_status=CLOSED
#	f1=ext_bz_bug_map.ext_bz_bug_id
#	list_id=7656791
#	o1=isnotempty
#	product=Red%20Hat%20Satellite%206
#	query_format=advanced
#
# https://bugzilla.redhat.com/buglist.cgi?f1=ext_bz_bug_map.ext_bz_bug_id&list_id=7656800&o1=isnotempty&product=Red%20Hat%20Satellite%206
# https://bugzilla.redhat.com/buglist.cgi?classification=Red%20Hat&f1=longdesc&list_id=7656856&o1=allwordssubstr&query_format=advanced&v1=https%3A%2F%2Fgithub.com
# https://bugzilla.redhat.com/buglist.cgi?classification=Red%20Hat&f1=ext_bz_bug_map.ext_bz_bug_id&f2=longdesc&list_id=7656917&o1=isnotempty&o2=allwords&query_format=advanced&v2=https%3A%2F%2Fgithub.com
#

def get_tickets():

    tickets_file = 'tickets.pickle'
    if os.path.isfile(tickets_file):
        with open(tickets_file, 'rb') as f:
            tickets = pickle.load(f)
        return tickets

    qs = 'https://bugzilla.redhat.com/buglist.cgi?classification=Red%20Hat&f1=ext_bz_bug_map.ext_bz_bug_id&f2=longdesc&o1=isnotempty&o2=allwords&query_format=advanced&v2=https%3A%2F%2Fgithub.com%2Fansible'
    query = bugzilla.url_to_query(qs)
    increment = 100 # 3k is the sweetspot
    increment = 3000
    query['limit'] = increment
    offset = 0
    tickets = []

    maxcount = 100
    maxcount = None

    while True:

        #if len(tickets) > 1:
        #    break

        if offset > 0:
            query['offset'] = offset

        print('# offset: %s' % offset)
        try:
            ntickets = bugzilla.query(query)
        except Exception as e:
            print('# error: %s' % e)
            break

        print('# total: ' + str(len(ntickets)))
        if len(ntickets) == 0:
            break

        for idt, ticket in enumerate(ntickets):
            tickets.append(ticket)
            if not hasattr(ticket, 'external_bugs'):
                continue
            if ticket.external_bugs:
                pprint(ticket.external_bugs)

        offset += increment

        if maxcount and  len(tickets) >= maxcount:
            break

    #with open(tickets_file, 'wb') as f:
    #    pickle.dump(tickets, f)

    return tickets


def _serialize_data(data):
    if isinstance(data, DateTime):
        # bson.errors.InvalidDocument: Cannot encode object: <DateTime
        # '20141215T13:52:01' at 7f60a9f5ccf8>
        ts = datetime.strptime(data.value, '%Y%m%dT%H:%M:%S').isoformat()
        data = ts
    elif isinstance(data, dict):
        for k,v in data.items():
            if isinstance(v, (dict, list, DateTime)) and v:
                data[k] = _serialize_data(v)
    elif isinstance(data, list) and data:
        for idx,x in enumerate(data):
            if isinstance(x, (dict, list, DateTime)) and x:
                data[idx] = _serialize_data(x)
    return data


def serialize_ticket(ticket):

    # refresh for external bugs
    if not hasattr(ticket, 'external_bugs'):
        try:
            ticket.refresh()
        except Exception as e:
            print(e)
        if not hasattr(ticket, 'external_bugs'):
            ticket.external_bugs = []

    data = {
        'url': ticket.weburl,
        'priority': ticket.priority,
        'product': ticket.product,
        'component': ticket.component,
        'state': 'closed',
        'external_bugs': []
    }
    if ticket.is_open:
        data['state'] = 'open'

    for ext in ticket.external_bugs:
        if 'type' in ext:
            if ext['ext_bz_bug_id'].startswith('http'):
                furl = ext['ext_bz_bug_id']
            else:
                furl = ext['type'].get('full_url')
                if '%id%' in furl:
                    furl = furl.replace('%id%', str(ext['ext_bz_bug_id']))
            data['external_bugs'].append(furl)

    return data


def process_tickets(tickets):

    client = pymongo.MongoClient()
    bzdb = client.bugzilla
    bugs = bzdb.bugs

    total = len(tickets)
    to_insert = []

    for idt,ticket in enumerate(tickets):

        if not bugs.find_one({'url': ticket.url}):
            sdata = serialize_ticket(ticket)
            print('%s|%s %s' % (total, idt, sdata['url']))
            to_insert.append(sdata)

        if len(to_insert) > 100 or (total - idt) < 100:
            print('inserting: %s' % [x['url'] for x in to_insert])
            bugs.insert_many(to_insert)
            to_insert = []

    client.close()


if __name__ == '__main__':

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    root.addHandler(ch)

    tickets = get_tickets()
    process_tickets(tickets)
    import epdb; epdb.st()
