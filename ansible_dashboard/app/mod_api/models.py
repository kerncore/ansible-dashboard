from pymongo import MongoClient

DBNAME = 'github_api'


class IssueModel(object):

    issueid = None
    is_pullrequest = False
    events = []
    _comments = []
    files = []
    reactions = []

    def __init__(self, issueid):
        self.issueid = issueid
        self.load()

    def load(self):
        client = MongoClient()
        db = getattr(client, DBNAME)

        issue = db.issues.find_one({'id': self.issueid})
        if issue:
            for k,v in issue.items():
                setattr(self, k, v)

            if 'pull' in issue['html_url']:
                self.is_pullrequest = True

                pull = db.issues.find_one({'issue_url': issue['url']})
                if pull:
                    for k,v in pull.items():
                        if not hasattr(self, k):
                            setattr(self, k, v)
                        else:
                            setattr(self, 'pull_' + k, v)

            self._comments = db.comments.find({'issue_url': issue['url']})

        client.close()
