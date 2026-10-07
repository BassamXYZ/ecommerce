#!/usr/bin/env bash
# Same steps as your build.sh, but run when the container starts
set -o errexit

python manage.py migrate --no-input
python manage.py collectstatic --no-input

if [[ -n "$CREATE_SUPERUSER" ]]; then
  # Needs DJANGO_SUPERUSER_USERNAME / EMAIL / PASSWORD in .env
  python manage.py createsuperuser --no-input || true
fi

exec "$@"
