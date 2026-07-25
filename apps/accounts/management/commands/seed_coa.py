"""Seed the Chart of Accounts (and optional default tax codes) for entities."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.accounts.services.seed import seed_entity_coa, seed_tax_codes
from apps.settings.services.driver_accounting import provision_driver_accounting
from apps.tenants.models import Entity


class Command(BaseCommand):
    help = "Seed the Chart of Accounts for an entity (by code/numeric_code) or all entities."

    def add_arguments(self, parser):
        parser.add_argument(
            "--entity",
            dest="entity",
            help="Entity code or numeric_code. Omit to seed all entities.",
        )
        parser.add_argument(
            "--tax",
            action="store_true",
            help="Also seed the default UAE VAT codes for each entity.",
        )

    def handle(self, *args, **options):
        qs = Entity.objects.all()
        if options.get("entity"):
            ident = options["entity"]
            qs = qs.filter(Q(code=ident) | Q(numeric_code=ident))
        if not qs.exists():
            self.stdout.write(self.style.WARNING("No matching entities."))
            return

        for entity in qs:
            result = seed_entity_coa(entity)
            line = (
                f"{entity.numeric_code} {entity.legal_name}: "
                f"+{result['groups_created']} groups, +{result['accounts_created']} accounts"
            )
            if options.get("tax"):
                tax_created = seed_tax_codes(entity)
                line += f", +{tax_created} tax codes"
            # Provision driver accounting once the CoA exists. Done here — the
            # entity provisioning orchestration point — rather than inside the
            # seeder, which would make the account template module depend on
            # settings. Idempotent; silent when no unambiguous account matches.
            config = provision_driver_accounting(entity)
            line += (
                f", driver receivable {config.default_receivable_account.code}"
                if config
                else ", driver receivable NOT configured"
            )
            self.stdout.write(self.style.SUCCESS(line))
