#!/usr/bin/env python3

import logging
from flask import g
from flask import redirect
from flask import url_for
from functools import wraps


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            guser = g.user
        except:
            guser = None
        logging.debug('guser: {}'.format(guser))

        if not guser:
            logging.error('redirecting to login')
            return redirect(url_for('login'))

        return f(*args, **kwargs)

    return wrapped
