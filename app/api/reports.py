"""
Reports API Router — Professional Examination Monitoring Reports.

Provides REST endpoints to list sessions, retrieve aggregated report summaries,
apply dynamic interactive filters, and export filtered reports.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Examination Reports"])


@router.get("/sessions")
def list_report_sessions():
    """
    List all available examination monitoring sessions (Live and Uploaded Video Feeds).
    """
    try:
        sessions = ReportService.list_available_sessions()
        return {"sessions": sessions}
    except Exception as ex:
        logger.exception("Failed to list report sessions: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@router.get("/session/{session_id}")
def get_session_report(
    session_id: str,
    risk_level: Optional[str] = Query(None, description="Filter by risk level: LOW, WATCH, HIGH, CRITICAL, or ALL"),
    event_type: Optional[str] = Query(None, description="Filter by event type substring"),
    camera_id: Optional[str] = Query(None, description="Filter by camera identifier"),
    seat_id: Optional[str] = Query(None, description="Filter by seat identifier"),
    track_id: Optional[str] = Query(None, description="Filter by anonymous track ID"),
    review_status: Optional[str] = Query(None, description="Filter by review status: PENDING, CONFIRMED, DISMISSED"),
    start_time: Optional[float] = Query(None, description="Start timestamp filter in seconds"),
    end_time: Optional[float] = Query(None, description="End timestamp filter in seconds"),
):
    """
    Retrieve comprehensive aggregated examination monitoring report for a given session.
    Applies interactive filters deterministically.
    """
    try:
        summary = ReportService.get_report_summary(
            session_id=session_id,
            risk_level=risk_level,
            event_type=event_type,
            camera_id=camera_id,
            seat_id=seat_id,
            track_id=track_id,
            review_status=review_status,
            start_time=start_time,
            end_time=end_time,
        )
        return summary
    except Exception as ex:
        logger.exception("Failed to generate session report for '%s': %s", session_id, ex)
        raise HTTPException(status_code=500, detail=str(ex))


@router.get("/session/{session_id}/export/csv")
def export_session_report_csv(
    session_id: str,
    risk_level: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    seat_id: Optional[str] = Query(None),
    track_id: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    start_time: Optional[float] = Query(None),
    end_time: Optional[float] = Query(None),
):
    """
    Export filtered examination report event logs as a CSV download.
    """
    try:
        summary = ReportService.get_report_summary(
            session_id=session_id,
            risk_level=risk_level,
            event_type=event_type,
            camera_id=camera_id,
            seat_id=seat_id,
            track_id=track_id,
            review_status=review_status,
            start_time=start_time,
            end_time=end_time,
        )

        events = summary.get("events_table", [])
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Event ID",
            "Timestamp",
            "Time String",
            "Track ID",
            "Seat ID",
            "Camera ID",
            "Event Type",
            "Severity",
            "Confidence",
            "Risk Score",
            "Review Status",
        ])

        for e in events:
            writer.writerow([
                e.get("event_id", ""),
                e.get("timestamp", ""),
                e.get("time_str", ""),
                e.get("track_id", ""),
                e.get("seat_id", ""),
                e.get("camera_id", ""),
                e.get("event_type", ""),
                e.get("severity", ""),
                e.get("confidence", ""),
                e.get("risk_score", ""),
                e.get("review_status", ""),
            ])

        output.seek(0)
        filename = f"copycop_report_{session_id.replace(' ', '_')}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as ex:
        logger.exception("Failed to export report CSV for '%s': %s", session_id, ex)
        raise HTTPException(status_code=500, detail=str(ex))
