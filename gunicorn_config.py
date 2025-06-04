# gunicorn_config.py
import os

# Force minimal workers for Heroku's 512MB memory limit
# Each worker loads the entire app, so fewer is better
workers = int(os.environ.get('WEB_CONCURRENCY', 2))
worker_class = 'uvicorn.workers.UvicornWorker'

# Timeout - set to 29 seconds (just under Heroku's 30-second limit)
timeout = 29
graceful_timeout = 29

# Keep alive
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Request handling - reduce to save memory
worker_connections = 500  # Reduced from 1000
max_requests = 500  # Reduced from 1000
max_requests_jitter = 50

# Memory optimization
preload_app = True  # Share memory between workers
max_requests = 500  # Restart workers periodically to prevent memory leaks
max_requests_jitter = 50