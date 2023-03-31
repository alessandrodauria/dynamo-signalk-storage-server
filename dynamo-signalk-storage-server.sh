#!/bin/bash

. venv/bin/activate

export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export FLASK_APP=dynamo-signalk-storage-server.py
export FLASK_ENV=development

flask run -h 0.0.0.0 -p 13388 # --no-reload
