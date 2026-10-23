#!/usr/bin/env bash
# Exit on error
set -o errexit

# Modify this line as needed for your package manager (pip, poetry, etc.)
pip install -r requirements.txt

# Convert static asset files
python manage.py collectstatic --no-input

# Apply any outstanding database migrations. On Neon, migrations should use the
# direct (unpooled) connection when DATABASE_URL_UNPOOLED is provided.
DATABASE_URL="${DATABASE_URL_UNPOOLED:-$DATABASE_URL}" python manage.py migrate

if [[ $CREATE_SUPERUSER ]]; then
  # Needs DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD. Not an error if it already exists.
  python manage.py createsuperuser --no-input || echo "Superuser already exists or could not be created."
fi
