from sqlalchemy import Column, String, ForeignKey
from app.database.session import Base

class AdministrativeSeatingRegistry(Base):
    """
    CRITICAL PRIVACY BOUNDARY:
    This table stores administrative identity mapping (Seat <-> Student).
    It is STRICTLY separated from the AI perception and behavioural pipeline.
    The AI system only processes Anonymous Track IDs and Seat references.
    Identity mapping is strictly optional and only accessible at human review stage.
    """
    __tablename__ = "admin_seating_registry"

    id = Column(String, primary_key=True, index=True)
    seat_id = Column(String, ForeignKey("seats.id"), nullable=False, unique=True)
    student_id_alias = Column(String, nullable=False) # Pseudonymized Administrative Roll ID
    full_name_encrypted = Column(String, nullable=False) # Administrative display name
