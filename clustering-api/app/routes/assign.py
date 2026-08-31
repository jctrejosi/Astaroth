from fastapi import APIRouter, HTTPException, status

from app.schemas.assign import AssignRequest
from app.services.assigner import Assigner

router = APIRouter()


@router.post("/assign")
def assign_points(request: AssignRequest):
    try:
        return Assigner.assign(request)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
