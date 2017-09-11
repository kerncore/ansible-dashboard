# Import flask dependencies
from flask import Blueprint, render_template

#from flask_login import login_required
from app.login_tools import login_required

from app.mod_api.models import IssueModel


# Define the blueprint: 'auth', set its url prefix: app.url/auth
mod_issues = Blueprint('mod_issues', __name__, url_prefix='/issues')


@mod_issues.route('/', methods=['GET', 'POST'])
@login_required
def index():
    issues = []
    return render_template("issues/index.html", form=None, issues=issues)


@mod_issues.route('/<int:issueid>', methods=['GET', 'POST'])
@login_required
def issue_view(issueid):
    issue = IssueModel(issueid)
    return render_template("issues/issue.html", form=None, issue=issue)
