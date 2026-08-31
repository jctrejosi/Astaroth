from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import Point


class AssignRequest(BaseModel):
    model_name: str = Field(..., min_length=1)

    points: List[Point] = Field(
        ...,
        min_length=1,
        description="Puntos a asignar (misma dimensionalidad con la que se entrenó)"
    )

    with_distances: bool = Field(
        True,
        description="Incluir la distancia de cada punto a cada centroide"
    )


class AssignResponse(BaseModel):
    model_name: str
    labels: List[int]
    distances: Optional[List[List[float]]] = None
