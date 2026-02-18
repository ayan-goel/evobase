#!/bin/sh
# Start the FastAPI server and Celery worker in the same container.
# Used by the combined Railway service in development / MVP.
#
# Both processes are started in the background; the script then waits
# for either to exit. If one crashes, the container exits and Railway
# restarts it (restart policy = on_failure).

set -e

echo "Starting Celery worker + beat..."
celery -A app.engine.queue worker --beat --loglevel=info --concurrency=2 &
CELERY_PID=$!

echo "Starting FastAPI server on port ${PORT:-8000}..."
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
UVICORN_PID=$!

# Exit as soon as either process dies so Railway can restart the container
wait -n $CELERY_PID $UVICORN_PID
echo "A process exited — shutting down"
kill $CELERY_PID $UVICORN_PID 2>/dev/null || true
