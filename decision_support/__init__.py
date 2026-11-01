"""DS-1 decision-support layer: operator-friendly reports from kbs_engine results."""
from .report import ReportBuilder, build_report, render_text

__all__ = ["ReportBuilder", "build_report", "render_text"]
