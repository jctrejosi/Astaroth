from typing import Optional

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    status: str
    model_name: str
    # Regresión temporal.
    mae: Optional[float] = None
    rmse: Optional[float] = None
    r2: Optional[float] = None
    # Propensión (clasificación).
    problem_type: Optional[str] = None
    metrics: Optional[dict[str, float]] = None