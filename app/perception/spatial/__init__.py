"""Spatial analysis sub-package — seat association and desk ROI."""

from app.perception.spatial.seat_manager import SeatManager
from app.perception.spatial.desk_roi import DeskROIEstimator

__all__ = ["SeatManager", "DeskROIEstimator"]
