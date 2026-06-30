"""WPS (Wage Protection System) — build the SIF batch and export the file.

A SIF is one Salary Control Record (employer header) plus one Employee Detail
Record per WPS-paid employee. The batch totals (records, fixed, variable) must
reconcile to the sum of records before the SIF file is produced. The SIF layout
(delimiter, version, record tags) is config-driven (``settings``), so MOHRE format
changes need no code edits.
"""

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.payroll.models import ComponentType, Employee, WpsBatch, WpsRecord
from apps.payroll.services.config import sif_layout
from apps.payroll.services.engine import ZERO, PayrollError, q


def _month_bounds(salary_month):
    year, month = (int(p) for p in salary_month.split("-"))
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1)
    return start, date.fromordinal(end.toordinal() - 1)


@transaction.atomic
def generate_wps(run, *, employer_eid, employer_bank_routing, user=None):
    """Build a WPS batch + records for the run's WPS-paid employees."""
    batch = WpsBatch.objects.create(
        run=run,
        employer_eid=employer_eid,
        employer_bank_routing=employer_bank_routing,
        salary_month=run.salary_month,
        generated_at=timezone.now(),
    )
    start, end = _month_bounds(run.salary_month)
    fixed_total = variable_total = ZERO
    count = 0
    payslips = run.payslips.filter(employee__pay_method=Employee.PayMethod.WPS).select_related(
        "employee"
    )
    for ps in payslips:
        fixed = variable = ZERO
        for ln in ps.lines.select_related("component"):
            if ln.component_type != ComponentType.EARNING:
                continue
            if ln.component.is_wps_fixed:
                fixed += q(ln.amount)
            else:
                variable += q(ln.amount)
        emp = ps.employee
        WpsRecord.objects.create(
            batch=batch,
            employee=emp,
            mol_personal_no=emp.mol_personal_no,
            bank_routing_code=emp.bank_routing_code,
            iban=emp.iban,
            pay_start_date=start,
            pay_end_date=end,
            working_days=ps.working_days,
            fixed_amount=fixed,
            variable_amount=variable,
        )
        fixed_total += fixed
        variable_total += variable
        count += 1

    batch.total_records = count
    batch.fixed_total = fixed_total
    batch.variable_total = variable_total
    batch.total_salary = q(fixed_total + variable_total)
    batch.save(
        update_fields=[
            "total_records",
            "fixed_total",
            "variable_total",
            "total_salary",
            "updated_at",
        ]
    )
    return batch


def _validate(batch):
    records = list(batch.records.all())
    if batch.total_records != len(records):
        raise PayrollError(f"SIF record count {batch.total_records} != {len(records)} records.")
    rec_total = sum((q(r.fixed_amount) + q(r.variable_amount) for r in records), ZERO)
    if q(batch.total_salary) != rec_total:
        raise PayrollError(f"SIF total {batch.total_salary} != record sum {rec_total}.")
    return records


def export_sif(batch, *, entity=None):
    """Validate totals and render the SIF content (config-driven layout)."""
    records = _validate(batch)
    layout = sif_layout(entity or batch.run.entity)
    delim = layout["delimiter"]
    lines = [
        delim.join(
            [
                layout["scr_tag"],
                batch.employer_eid,
                batch.employer_bank_routing,
                batch.salary_month,
                str(batch.total_records),
                f"{q(batch.total_salary)}",
            ]
        )
    ]
    for r in records:
        lines.append(
            delim.join(
                [
                    layout["edr_tag"],
                    r.mol_personal_no,
                    r.bank_routing_code,
                    r.iban,
                    r.pay_start_date.isoformat(),
                    r.pay_end_date.isoformat(),
                    f"{r.working_days}",
                    f"{q(r.fixed_amount)}",
                    f"{q(r.variable_amount)}",
                ]
            )
        )
    content = "\n".join(lines)
    batch.sif_file_ref = f"SIF_{batch.employer_eid}_{batch.salary_month}.csv"
    batch.save(update_fields=["sif_file_ref", "updated_at"])
    return content
