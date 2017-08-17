#!/usr/bin/env python3

import json
import os
import subprocess
from pymongo import MongoClient


def run_command(args):
    p = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (so, se) = p.communicate()
    return (p.returncode, so, se)


def get_collection_ids(db, collection_name, field='id'):
    collection = getattr(db, collection_name)
    pipeline = [
        {'$project': {'_id': 0, field:1}}
    ]
    cursor = collection.aggregate(pipeline)
    res = list(cursor)
    res = [(x[field], True) for x in res]
    res = dict(res)
    return res


def get_collection_timestamps(db, collection_name, field='updated_at'):
    collection = getattr(db, collection_name)
    pipeline = [
        {'$project': {'_id': 0, 'url':1, field: 1}}
    ]
    cursor = collection.aggregate(pipeline)
    res = list(cursor)
    try:
        res = [(x['url'], x[field]) for x in res]
    except KeyError as e:
        print(e)
        import epdb; epdb.st()
    res = dict(res)
    return res


def main():

    collection_whitelist = ['issues', 'pulls', 'comments', 'events', 'commits', 'files', 'reactions']

    client = MongoClient()
    db = client.github_api

    ids = {
        'comments': get_collection_ids(db, 'comments'),
        'events': get_collection_ids(db, 'events'),
        'reactions': get_collection_ids(db, 'reactions'),
        'files': get_collection_ids(db, 'pullrequest_files', field='sha')
    }

    timestamps = {
        'issues': get_collection_timestamps(db, 'issues'),
        'pullrequests': get_collection_timestamps(db, 'pullrequests')
    }


    fcmd = 'cd ~ ; find ansible.data -type f -name "*.json" | fgrep -v credentials'
    (rc, so, se) = run_command(fcmd)
    so = so.decode("utf-8")
    jfiles = sorted(set(so.split('\n')))

    for jfile in jfiles:
        print(jfile)

        bname = os.path.basename(jfile)
        if bname != 'data.json':
            print('\tskipping1')
            continue

        dirname = os.path.dirname(jfile)
        dirname = os.path.basename(dirname)

        '''
        if dirname.isnumeric():
            dirname = os.path.dirname(jfile)
            dirname = os.path.dirname(dirname)
            dirname = os.path.basename(dirname)
            import epdb; epdb.st()
        '''

        if dirname.isnumeric():
            thisnumber = int(dirname)
            dirname = os.path.dirname(jfile)
            dirname = os.path.dirname(dirname)
            dirname = os.path.basename(dirname)
            #import epdb; epdb.st()
        else:
            thisnumber = os.path.dirname(os.path.dirname(jfile))
            thisnumber = os.path.basename(thisnumber)
            try:
                thisnumber = int(thisnumber)
            except ValueError as e:
                print(e)
                #import epdb; epdb.st()
                print('\tskipping3')
                continue

        if dirname not in collection_whitelist:
            print('\tskipping2 {}'.format(dirname))
            continue


        repoidx = jfile.index(str(thisnumber))
        repopath = jfile[:repoidx]
        repopath = repopath.replace('ansible.data/', '', 1)
        repoparts = repopath.split('/')
        repoparts = [x.strip() for x in repoparts if x.strip()]
        repopath = '/'.join(repoparts[0:2])

        # 'issue_url': 'https://api.github.com/repos/ansible/ansible-modules-core/issues/1',
        issue_url = 'https://api.github.com/repos/{}/issues/{}'.format(repopath, thisnumber)
        pull_url = 'https://api.github.com/repos/{}/pulls/{}'.format(repopath, thisnumber)

        with open(jfile, 'rb') as f:
            jdata = json.loads(f.read())

        if not jdata:
            print('no data in {}'.format(jfile))
            os.remove(jfile)
            print('\tskipping4')
            continue

        if isinstance(jdata, dict) and 'documentation_url' in jdata:
            continue

        collection = None
        if dirname in ['comments', 'events', 'reactions']:
            collection = getattr(db, dirname)
            for xc in jdata:
                if 'issue_url' not in xc:
                    try:
                        xc['issue_url'] = issue_url
                    except Exception as e:
                        print(e)
                        import epdb; epdb.st()

                #res = collection.find_one({'id': xc['id']})
                #if not res:
                #    collection.insert(xc)

                if xc['id'] not in ids[dirname]:
                    collection.insert(xc)

        elif dirname == 'files':
            collection = getattr(db, 'pullrequest_files')
            for xf in jdata:
                xf['pullrequest_url'] = pull_url
                xf['issue_url'] = issue_url
                if xf['sha'] not in ids['files']:
                    collection.insert(xf)
                #import epdb; epdb.st()

        elif dirname == 'issues':
            collection = getattr(db, dirname)
            if issue_url not in timestamps['issues']:
                collection.insert(jdata)
            elif timestamps['issues'][issue_url] < jdata['updated_at']:
                collection.replace_one(jdata, {'url': issue_url}, True)
            else:
                print('\tskipping5')

        elif dirname == 'pulls':
            collection = getattr(db, 'pullrequests')
            if pull_url not in timestamps['pullrequests']:
                collection.insert(jdata)
            elif timestamps['pullrequests'][pull_url] < jdata['updated_at']:
                collection.replace_one(jdata, {'url': pull_url}, True)
            else:
                print('\tskipping5')
            #import epdb; epdb.st()

        #else:
        #    import epdb; epdb.st()


    client.close()


if __name__ == "__main__":
    main()