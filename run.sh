#!/bin/bash

vagrant up --provider=virtualbox

vagrant rsync-auto
