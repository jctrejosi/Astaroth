from typing import Optional

from pydantic import BaseModel


class ModelInfo(BaseModel):
    model_name: str
    target_column: str
    trained_at: Optional[str] = None
    records: int
    features: int
    lags: Optional[int] = None
    test_size: Optional[float] = None
    mae: Optional[float] = None
    rmse: Optional[float] = None
    r2: Optional[float] = None
    feature_columns: Optional[list[str]] = None
    # Modelos de propensión: no tienen métricas de regresión.
    problem_type: Optional[str] = None
    metrics: Optional[dict[str, float]] = None


class ModelListResponse(BaseModel):
    count: int
    models: list[ModelInfo]


class ModelDetailResponse(BaseModel):
    status: str
    model: ModelInfo