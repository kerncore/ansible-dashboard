#!/bin/bash

while true; do
    rsync -avz . --exclude 'ansibullbot/app/config.py' root@dash:~dashboard/src/ansible-dashboard
    ssh root@dash 'cp -f ~dashboard/config.py ~dashboard/src/ansible-dashboard/ansible_dashboard/.'
    sleep 3
done
