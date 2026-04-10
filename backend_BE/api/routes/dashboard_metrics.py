from typing import Literal

from fastapi import APIRouter, Query

from services.dashboard_metrics_service import metrics_store


router = APIRouter(prefix="/dashboard", tags=["Dashboard Metrics"])


RangeType = Literal["24h", "7d", "30d"]
SourceType = Literal["all", "threat", "log"]


@router.get("/stats")
async def get_dashboard_stats(source: SourceType = Query(default="all")):
    return metrics_store.get_stats(source=source)


@router.get("/severity")
async def get_dashboard_severity(
    range: RangeType = Query(default="30d"),  # noqa: A002
    source: SourceType = Query(default="all"),
):
    return metrics_store.get_severity_breakdown(range_value=range, source=source)


@router.get("/recent-alerts")
async def get_dashboard_recent_alerts(
    limit: int = Query(default=10, ge=1, le=100),
    source: SourceType = Query(default="all"),
):
    return metrics_store.get_recent_alerts(limit=limit, source=source)


@router.get("/metrics")
async def get_dashboard_metrics(
    range: RangeType = Query(default="30d"),  # noqa: A002
    source: SourceType = Query(default="all"),
    recent_limit: int = Query(default=10, ge=1, le=100),
):
    return metrics_store.get_metrics(range_value=range, source=source, recent_limit=recent_limit)


@router.delete("/clear")
async def clear_dashboard_metrics(source: SourceType = Query(default="all")):
    return metrics_store.clear_metrics(source=source)
