"""
    GitHub Example
    --------------

    Shows how to authorize users with Github.

"""
from flask import Flask, request, g, session, redirect, url_for
from flask import render_template
from flask import render_template_string
from flask_github import GitHub

from flask_bootstrap import Bootstrap

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# setup flask
app = Flask(__name__)
app.config.from_object('config')

# setup bootstrap
Bootstrap(app)

# setup github-flask
github = GitHub(app)

# setup sqlalchemy
engine = create_engine(app.config['DATABASE_URI'])
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


def init_db():
    Base.metadata.create_all(bind=engine)

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

from app.mod_api.controllers import mod_api_bp as api_module
app.register_blueprint(api_module)

from app.mod_tokens.controllers import mod_tokens as tokens_module
app.register_blueprint(tokens_module)

from app.mod_repos.controllers import mod_repos as repos_module
app.register_blueprint(repos_module)

from app.mod_search.controllers import mod_search as search_module
app.register_blueprint(search_module)

from app.mod_issues.controllers import mod_issues as issues_module
app.register_blueprint(issues_module)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(200))
    github_access_token = Column(String(200))

    def __init__(self, github_access_token):
        self.github_access_token = github_access_token


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.get(session['user_id'])


@app.after_request
def after_request(response):
    db_session.remove()
    return response


@app.route('/')
def index():
    if g.user:
        t = 'Hello! <a href="{{ url_for("user") }}">Get user</a> ' \
            '<a href="{{ url_for("logout") }}">Logout</a>'
    else:
        t = 'Hello! <a href="{{ url_for("login") }}">Login</a>'
        return render_template_string(t)

    return render_template('index.html')


@github.access_token_getter
def token_getter():
    user = g.user
    if user is not None:
        return user.github_access_token


@app.route('/github-callback')
@app.route('/login/authorized')
@github.authorized_handler
def authorized(access_token):
    next_url = request.args.get('next') or url_for('index')
    if access_token is None:
        return redirect(next_url)

    user = User.query.filter_by(github_access_token=access_token).first()

    if user is None:
        user = User(access_token)
        db_session.add(user)
    user.github_access_token = access_token
    db_session.commit()

    session['user_id'] = user.id
    return redirect(next_url)


@app.route('/login')
def login():
    if session.get('user_id', None) is None:
        return github.authorize()
    else:
        return 'Already logged in'


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/user')
def user():
    return str(github.get('user'))


#if __name__ == '__main__':
#    init_db()
#    app.run(host='0.0.0.0', debug=True)
