"""Exam Hall Physical Layout and Seat Coordinate Topology."""
import math
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class SeatLocation(BaseModel):
    seat_id: str
    row_idx: int
    col_idx: int
    x: float  # Normalized hall coordinate (0.0 to 1.0)
    y: float  # Normalized hall coordinate (0.0 to 1.0)
    desk_x_min: float
    desk_y_min: float
    desk_x_max: float
    desk_y_max: float


class ExamHallLayout:
    """Represents the seating grid, physical spacing, and neighborhood metrics of an exam hall."""

    def __init__(
        self,
        rows: int = 4,
        cols: int = 5,
        row_labels: Optional[List[str]] = None,
        desk_width: float = 0.12,
        desk_height: float = 0.08,
        aisle_gap_col: int = 2,  # Aisle between col 2 and 3
    ):
        self.rows = rows
        self.cols = cols
        self.row_labels = row_labels or ["A", "B", "C", "D", "E", "F"][:rows]
        self.desk_width = desk_width
        self.desk_height = desk_height
        self.aisle_gap_col = aisle_gap_col

        self.seats: Dict[str, SeatLocation] = {}
        self._build_grid()

    def _build_grid(self):
        """Build normalized (x, y) coordinates for all desks."""
        x_margin = 0.08
        y_margin = 0.12
        available_w = 1.0 - (2 * x_margin)
        available_h = 1.0 - (2 * y_margin)

        x_step = available_w / max(self.cols - 1, 1)
        y_step = available_h / max(self.rows - 1, 1)

        for r_idx, r_label in enumerate(self.row_labels):
            for c_idx in range(self.cols):
                seat_id = f"{r_label}{c_idx + 1}"
                
                # Add extra spacing for central aisle
                aisle_offset = 0.04 if c_idx >= self.aisle_gap_col else 0.0
                
                cx = x_margin + (c_idx * x_step) + aisle_offset
                cy = y_margin + (r_idx * y_step)

                # Clamp to [0, 1]
                cx = min(max(cx, 0.05), 0.95)
                cy = min(max(cy, 0.05), 0.95)

                self.seats[seat_id] = SeatLocation(
                    seat_id=seat_id,
                    row_idx=r_idx,
                    col_idx=c_idx,
                    x=round(cx, 3),
                    y=round(cy, 3),
                    desk_x_min=round(cx - (self.desk_width / 2.0), 3),
                    desk_y_min=round(cy - (self.desk_height / 2.0), 3),
                    desk_x_max=round(cx + (self.desk_width / 2.0), 3),
                    desk_y_max=round(cy + (self.desk_height / 2.0), 3),
                )

    def get_seat(self, seat_id: str) -> Optional[SeatLocation]:
        return self.seats.get(seat_id)

    def get_distance(self, seat_id_1: str, seat_id_2: str) -> float:
        """Physical distance in hall coordinates."""
        s1 = self.get_seat(seat_id_1)
        s2 = self.get_seat(seat_id_2)
        if not s1 or not s2:
            return 999.0
        return math.hypot(s1.x - s2.x, s1.y - s2.y)

    def get_relative_direction(self, from_seat_id: str, to_seat_id: str) -> str:
        """Returns LEFT, RIGHT, FRONT, BACK, or DIAGONAL."""
        s1 = self.get_seat(from_seat_id)
        s2 = self.get_seat(to_seat_id)
        if not s1 or not s2:
            return "UNKNOWN"

        d_row = s2.row_idx - s1.row_idx
        d_col = s2.col_idx - s1.col_idx

        if d_row == 0 and d_col == 1:
            return "RIGHT"
        elif d_row == 0 and d_col == -1:
            return "LEFT"
        elif d_row == -1 and d_col == 0:
            return "FRONT"
        elif d_row == 1 and d_col == 0:
            return "BACK"
        elif abs(d_row) <= 1 and abs(d_col) <= 1:
            return "DIAGONAL"
        return "FAR"

    def is_immediate_neighbor(self, seat_id_1: str, seat_id_2: str) -> bool:
        s1 = self.get_seat(seat_id_1)
        s2 = self.get_seat(seat_id_2)
        if not s1 or not s2:
            return False
        d_row = abs(s1.row_idx - s2.row_idx)
        d_col = abs(s1.col_idx - s2.col_idx)
        return (d_row <= 1 and d_col <= 1) and not (d_row == 0 and d_col == 0)
