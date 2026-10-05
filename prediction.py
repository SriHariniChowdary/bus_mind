"""Demo ETA and delay prediction using generated training data."""

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor


def train_models():
    """Train lightweight models on reproducible synthetic examples."""
    rng = np.random.default_rng(42)
    distance = rng.uniform(0.5, 30, 500)
    speed = rng.uniform(8, 55, 500)
    traffic = rng.uniform(0, 25, 500)
    delay = rng.uniform(0, 20, 500)

    eta = distance / np.maximum(speed, 5) * 60 + traffic + delay
    features = np.column_stack([distance, speed, traffic, delay])

    eta_model = RandomForestRegressor(n_estimators=60, random_state=42)
    eta_model.fit(features, eta)

    labels = np.where(eta < 20, 0, np.where(eta < 45, 1, 2))
    delay_model = RandomForestClassifier(n_estimators=60, random_state=42)
    delay_model.fit(features, labels)
    return eta_model, delay_model


try:
    ETA_MODEL, DELAY_MODEL = train_models()
except Exception:
    ETA_MODEL = DELAY_MODEL = None


def predict_eta(distance_km: float, speed_kmh: float, traffic_minutes: float, delay_minutes: float) -> float:
    features = np.array([[distance_km, max(speed_kmh, 5), traffic_minutes, delay_minutes]])
    try:
        if ETA_MODEL is None:
            raise RuntimeError("Model unavailable")
        return max(1.0, float(ETA_MODEL.predict(features)[0]))
    except Exception:
        return max(1.0, distance_km / max(speed_kmh, 5) * 60 + traffic_minutes + delay_minutes)


def predict_delay(distance_km: float, speed_kmh: float, traffic_minutes: float, delay_minutes: float):
    """Return (category, estimated delay minutes)."""
    features = np.array([[distance_km, max(speed_kmh, 5), traffic_minutes, delay_minutes]])
    try:
        if DELAY_MODEL is None:
            raise RuntimeError("Model unavailable")
        label = int(DELAY_MODEL.predict(features)[0])
    except Exception:
        label = 0 if delay_minutes < 5 else (1 if delay_minutes < 15 else 2)

    category = ["On Time", "Slightly Delayed", "Highly Delayed"][label]
    return category, round(float(delay_minutes + traffic_minutes * 0.35), 1)
