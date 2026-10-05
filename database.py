"""SQLite database setup and data access for BusMind."""

import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv()

DB_PATH = os.getenv("BUSMIND_DB", "busmind.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, default=10)
    travel_minutes: Mapped[int] = mapped_column(Integer, default=30)
    # Stops are stored as a simple comma-separated list for demo simplicity.
    stops_text: Mapped[str] = mapped_column(String, default="")
    coordinates_text: Mapped[str] = mapped_column(String, default="")

    buses: Mapped[list["Bus"]] = relationship(back_populates="route")


class Bus(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    latitude: Mapped[float] = mapped_column(Float, default=17.385)
    longitude: Mapped[float] = mapped_column(Float, default=78.4867)
    speed_kmh: Mapped[float] = mapped_column(Float, default=25)
    status: Mapped[str] = mapped_column(String, default="Moving")
    next_stop: Mapped[str] = mapped_column(String, default="Central Stop")
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    route: Mapped[Route] = relationship(back_populates="buses")


class LocationHistory(Base):
    __tablename__ = "location_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bus_number: Mapped[str] = mapped_column(String, index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bus_number: Mapped[str] = mapped_column(String)
    prediction_type: Mapped[str] = mapped_column(String)
    result: Mapped[str] = mapped_column(String)
    predicted_minutes: Mapped[float] = mapped_column(Float, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def route_coordinates(route: Route) -> list[tuple[float, float]]:
    """Convert a route's saved coordinate string to latitude/longitude pairs."""
    try:
        return [
            tuple(map(float, pair.split(":")))
            for pair in route.coordinates_text.split("|")
            if pair.strip()
        ]
    except (ValueError, AttributeError):
        return []


def initialize_database() -> None:
    """Create tables and populate a small sample network if it is empty."""
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        if db.query(Route).count() == 0:
            routes = [
                Route(
                    name="Route A",
                    source="City Center",
                    destination="Hyderabad Airport",
                    distance_km=28.0,
                    travel_minutes=55,
                    stops_text="City Center, Lakdi-ka-pul, Mehdipatnam, Airport",
                    coordinates_text=(
                        "17.3850:78.4867|17.3990:78.4600|"
                        "17.3190:78.4260|17.2403:78.4294"
                    ),
                ),
                Route(
                    name="Route B",
                    source="Secunderabad",
                    destination="HITEC City",
                    distance_km=22.0,
                    travel_minutes=50,
                    stops_text="Secunderabad, Begumpet, Ameerpet, HITEC City",
                    coordinates_text=(
                        "17.4399:78.4983|17.4440:78.4660|"
                        "17.4375:78.4483|17.4435:78.3772"
                    ),
                ),
                Route(
                    name="Route C",
                    source="Miyapur",
                    destination="Charminar",
                    distance_km=26.0,
                    travel_minutes=60,
                    stops_text="Miyapur, Kukatpally, Ameerpet, Charminar",
                    coordinates_text=(
                        "17.4968:78.3615|17.4849:78.4138|"
                        "17.4375:78.4483|17.3616:78.4747"
                    ),
                ),
            ]
            db.add_all(routes)
            db.flush()

            route_by_name = {route.name: route for route in routes}
            samples = [
                ("101", "Route A", 17.3850, 78.4867, 32, "Moving", "Lakdi-ka-pul", 0),
                ("102", "Route A", 17.3190, 78.4260, 14, "Delayed", "Airport", 12),
                ("201", "Route B", 17.4375, 78.4483, 0, "Stopped", "Ameerpet", 3),
                ("301", "Route C", 17.4849, 78.4138, 27, "Moving", "Ameerpet", 0),
                ("401", "Route B", 17.4435, 78.3772, 0, "Inactive", "HITEC City", 0),
            ]
            for number, route_name, lat, lon, speed, status, stop, delay in samples:
                db.add(
                    Bus(
                        number=number,
                        route_id=route_by_name[route_name].id,
                        latitude=lat,
                        longitude=lon,
                        speed_kmh=speed,
                        status=status,
                        next_stop=stop,
                        delay_minutes=delay,
                    )
                )

        db.commit()


def save_location(db, bus: Bus) -> None:
    """Save the bus's current location as a history record."""
    db.add(
        LocationHistory(
            bus_number=bus.number,
            latitude=bus.latitude,
            longitude=bus.longitude,
            speed_kmh=bus.speed_kmh,
            status=bus.status,
        )
    )


def save_prediction(db, bus_number: str, kind: str, result: str, minutes: float = 0) -> None:
    db.add(
        PredictionResult(
            bus_number=bus_number,
            prediction_type=kind,
            result=result,
            predicted_minutes=minutes,
        )
    )
