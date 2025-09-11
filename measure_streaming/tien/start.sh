#!/bin/bash
# Start NGINX
nginx

# Start Flask app
gunicorn  -b 0.0.0.0:5000 main:app
