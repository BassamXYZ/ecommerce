from datetime import timedelta

from django.core.management.base import BaseCommand

from app.services import PENDING_ORDER_TTL, expire_stale_orders


class Command(BaseCommand):
    help = "Fail unpaid orders older than the given age and release their reserved stock."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=int(PENDING_ORDER_TTL.total_seconds() // 60),
            help="Age in minutes after which an unpaid order expires (default: %(default)s).",
        )

    def handle(self, *args, **options):
        count = expire_stale_orders(max_age=timedelta(minutes=options["minutes"]))
        self.stdout.write(self.style.SUCCESS(f"Expired {count} unpaid order(s)."))
