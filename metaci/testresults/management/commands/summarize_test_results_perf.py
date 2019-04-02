import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import F, Count, Value
from django.db import models

from metaci.build.models import BuildFlow
from metaci.testresults.models import TestResultPerfSummary, TestResult

from metaci.api.views.testmethod_perf import TestMethodPerfFilterSet

DATE_FORMAT = "%Y-%m-%d"


def date_range(startString, endString):
    start = datetime.datetime.strptime(startString, DATE_FORMAT)
    end = datetime.datetime.strptime(endString, DATE_FORMAT)
    date_generated = (
        start + datetime.timedelta(days=x) for x in range(0, (end - start).days)
    )

    for date in date_generated:
        yield date.strftime(DATE_FORMAT)


class Command(BaseCommand):
    # NOTE: This should only be run at heroku postdeploy stage
    help = "Build rows in testresult_perfsummaries table for a single date"
    metrics = {
        name: f.aggregation for (name, f) in TestMethodPerfFilterSet.metrics.items()
    }
    annotations = [
        "count",
        "duration_average",
        "duration_slow",
        "duration_fast",
        "cpu_usage_average",
        "cpu_usage_low",
        "cpu_usage_high",
        "failures",
    ]

    def add_arguments(self, parser):
        parser.add_argument("startdate", type=str)
        parser.add_argument("enddate", type=str)
        parser.add_argument("replace", choices=["replace", "continue"])

    def handle_date(self, date):
        metrics = self.metrics
        date_with_timezone = timezone.template_localtime(date, use_tz=True)
        buildflows = BuildFlow.objects.filter(time_end__date=date_with_timezone)

        method_contexts = (
            TestResult.objects.filter(build_flow_id__in=buildflows)
            .values(
                "method_id",
                repo_id=F("build_flow__build__repo"),
                branch_id=F("build_flow__build__branch"),
                plan_id=F("build_flow__build__plan"),
                flow=F("build_flow__flow"),
                day=Value(date, output_field=models.DateField()),
            )
            .annotate(
                count=Count("method__name"),
                duration_average=metrics["duration_average"],
                duration_slow=metrics["duration_slow"],
                duration_fast=metrics["duration_fast"],
                cpu_usage_average=metrics["cpu_usage_average"],
                cpu_usage_low=metrics["cpu_usage_low"],
                cpu_usage_high=metrics["cpu_usage_high"],
                failures=metrics["failures"],
            )
        )

        print(method_contexts.query)
        obsolete_objects = TestResultPerfSummary.objects.filter(day=date)
        print("To delete", len(obsolete_objects))
        obsolete_objects.delete()

        new_objects = [TestResultPerfSummary(**values) for values in method_contexts]
        print(len(new_objects))

        print(len(TestResultPerfSummary.objects.bulk_create(new_objects)))

    def handle(self, startdate, enddate, replace, **options):
        should_replace = replace == "replace"
        if not should_replace:
            try:
                last_day_processed = TestResultPerfSummary.objects.order_by("-day")[
                    0
                ].day
                # replace last day processed even if mode is not "replace".
                # often we won't have a way of knowing if the last day is
                # complete
                startdate = max(startdate, last_day_processed.strftime(DATE_FORMAT))
            except IndexError:
                pass
        dates = date_range(startdate, enddate)
        for date in dates:
            self.handle_date(date)
