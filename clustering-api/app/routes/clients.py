"""Clientes RFM con su segmento, features y contacto.

Sirve a la UI de campañas para: (1) listar TODOS los clientes con su
probabilidad de compra (analítica) y (2) segmentar manualmente por
filtros sobre los atributos de la réplica. El scoring (propensión /
uplift) lo orquesta el backend del ecommerce con xgboost/uplift.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import verify_admin_key
from app.services.assigner import Assigner
from app.services.db import DatabaseError, read_features
from app.services.model_store import ModelStore
from app.services.segmenter import RFM_ID_COLUMN, RFM_QUERY, _client_contacts

router = APIRouter()

# Features numéricas del modelo RFM (mismas que consume xgboost/uplift).
FEATURES = ("frecuencia", "monetario", "ticket_promedio", "categorias_distintas")

MAX_LIMIT = 100000


class ClientsFilters(BaseModel):
    segment: Optional[int] = Field(None, description="Solo clientes de este segmento")
    min_frecuencia: Optional[float] = None
    max_frecuencia: Optional[float] = None
    min_monetario: Optional[float] = None
    max_monetario: Optional[float] = None
    min_ticket_promedio: Optional[float] = None
    max_ticket_promedio: Optional[float] = None
    min_categorias_distintas: Optional[float] = None
    max_categorias_distintas: Optional[float] = None
    cedulas: Optional[list[str]] = Field(
        None, description="Solo estos clientes (cédula/NIT)"
    )


class SegmentClientsRequest(BaseModel):
    model_name: str = "seg_rfm_v1"
    filters: ClientsFilters = Field(default_factory=ClientsFilters)
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=MAX_LIMIT)
    with_contacts: bool = True


@router.post(
    "/segment-clients",
    dependencies=[Depends(verify_admin_key)],
)
def segment_clients(request: SegmentClientsRequest):
    """Clientes de la réplica RFM con segmento, features y contacto (filtrable)."""
    try:
        ids, feature_names, X = read_features(RFM_QUERY, RFM_ID_COLUMN)
        metadata = ModelStore.load_metadata(request.model_name)
        expected = metadata.get("feature_names")
        if expected is not None and feature_names != expected:
            raise ValueError(
                f"las features de la consulta no coinciden con el modelo: "
                f"esperaba {expected}, recibió {feature_names}"
            )
        result = Assigner.assign_matrix(request.model_name, X)
        labels = result["labels"]

        feat_names = [n for n in FEATURES if n in feature_names]
        feat_idx = {n: feature_names.index(n) for n in feat_names}

        f = request.filters
        cedulas_set = set(f.cedulas or [])
        matched: list[dict] = []
        for i, cedula in enumerate(ids):
            seg = labels[i]
            if f.segment is not None and seg != f.segment:
                continue
            if cedulas_set and cedula not in cedulas_set:
                continue
            features = {n: float(X[i][feat_idx[n]]) for n in feat_names}
            if f.min_frecuencia is not None and features.get("frecuencia", 0) < f.min_frecuencia:
                continue
            if f.max_frecuencia is not None and features.get("frecuencia", 0) > f.max_frecuencia:
                continue
            if f.min_monetario is not None and features.get("monetario", 0) < f.min_monetario:
                continue
            if f.max_monetario is not None and features.get("monetario", 0) > f.max_monetario:
                continue
            if f.min_ticket_promedio is not None and features.get("ticket_promedio", 0) < f.min_ticket_promedio:
                continue
            if f.max_ticket_promedio is not None and features.get("ticket_promedio", 0) > f.max_ticket_promedio:
                continue
            if f.min_categorias_distintas is not None and features.get("categorias_distintas", 0) < f.min_categorias_distintas:
                continue
            if f.max_categorias_distintas is not None and features.get("categorias_distintas", 0) > f.max_categorias_distintas:
                continue
            matched.append({"cedula": cedula, "segment": seg, "features": features})

        total = len(matched)
        page = matched[request.offset : request.offset + request.limit]

        if request.with_contacts and page:
            contacts = _client_contacts([r["cedula"] for r in page])
            for r in page:
                c = contacts.get(r["cedula"], {})
                r["name"] = c.get("name")
                r["email"] = c.get("email")
                r["phone"] = c.get("phone")
                r["consent_email"] = c.get("consent_email", False)
                r["consent_whatsapp"] = c.get("consent_whatsapp", False)
                r["consent_sms"] = c.get("consent_sms", False)

        return {
            "model_name": request.model_name,
            "total": total,
            "offset": request.offset,
            "clients": page,
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
