#!/usr/bin/env python3

import subprocess

from pymongo import MongClient

def run_command(args):
    p = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (so, se) = p.communicate()
    return (p.returncode, so, se)

def main():
    fcmd = 'cd ~ ; find ansible.data -type d'
    (rc, so, se) = run_command(fcmd)
    so = so.decode("utf-8")
    directories = so.split('\n')
    import epdb; epdb.st()


if __name__ == "__main__":
    main()