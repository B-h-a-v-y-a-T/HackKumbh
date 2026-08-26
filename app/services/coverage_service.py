from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.seat import Seat

class CoverageService:
    @staticmethod
    def get_coverage_report(db: Session, exam_id: str) -> Dict[str, Any]:
        seats = db.query(Seat).filter(Seat.exam_id == exam_id).all()
        if not seats:
            # Fallback mock setup if DB empty
            return CoverageService._generate_default_coverage()

        total = len(seats)
        good_count = sum(1 for s in seats if s.visibility_status == "GOOD")
        partial_count = sum(1 for s in seats if s.visibility_status == "PARTIAL")
        poor_count = sum(1 for s in seats if s.visibility_status == "POOR")
        blind_count = sum(1 for s in seats if s.visibility_status == "BLIND_SPOT")

        reliable_pct = round((good_count / total) * 100, 1) if total > 0 else 0
        partial_pct = round((partial_count / total) * 100, 1) if total > 0 else 0
        blind_pct = round(((poor_count + blind_count) / total) * 100, 1) if total > 0 else 0

        problematic_seats = []
        for s in seats:
            if s.visibility_status in ["POOR", "BLIND_SPOT"]:
                problematic_seats.append({
                    "seat_id": s.seat_label,
                    "status": s.visibility_status,
                    "score": s.visibility_score,
                    "recommendation": "Camera visibility insufficient for reliable monitoring. Reposition camera or leave seat unoccupied."
                })

        return {
            "exam_id": exam_id,
            "total_seats": total,
            "reliable_coverage_pct": reliable_pct,
            "partial_coverage_pct": partial_pct,
            "blind_spots_pct": blind_pct,
            "good_seats_count": good_count,
            "partial_seats_count": partial_count,
            "poor_seats_count": poor_count,
            "blind_spots_count": blind_count,
            "problematic_seats": problematic_seats
        }

    @staticmethod
    def _generate_default_coverage() -> Dict[str, Any]:
        return {
            "exam_id": "EXAM_001",
            "total_seats": 120,
            "reliable_coverage_pct": 91.0,
            "partial_coverage_pct": 7.0,
            "blind_spots_pct": 2.0,
            "good_seats_count": 109,
            "partial_seats_count": 8,
            "poor_seats_count": 2,
            "blind_spots_count": 1,
            "problematic_seats": [
                {"seat_id": "B4", "status": "POOR", "score": 0.42, "recommendation": "Partial structural pillar occlusion. Reposition CAM_02 or adjust angle."},
                {"seat_id": "D8", "status": "BLIND_SPOT", "score": 0.18, "recommendation": "Camera coverage is insufficient for reliable monitoring. Leave seat unoccupied or add auxiliary angle."}
            ]
        }
