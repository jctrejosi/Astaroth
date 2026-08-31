from fastapi import APIRouter, HTTPException, status

from app.schemas.fit import FitRequest
from app.services.clusterer import Clusterer

router = APIRouter()


@router.post("/fit")
def fit_model(request: FitRequest):
    try:
        return Clusterer.fit(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el entrenamiento: {e}"
        )
