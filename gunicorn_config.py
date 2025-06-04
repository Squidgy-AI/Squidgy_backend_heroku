# gunicorn_config.py - Create this file in your root directory
import multiprocessing

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
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

# Request handling
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50