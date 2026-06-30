"""Report catalog routes (mounted under /api/v1/reports/)."""

from django.urls import path

from apps.reports.views import ReportView

urlpatterns = [
    path("<str:code>/", ReportView.as_view(), name="report-catalog"),
]
