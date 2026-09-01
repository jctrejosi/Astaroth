import math
import json

from flask import Blueprint, request, jsonify

from .handlers.consult_model import llm_handler
from .handlers.file_converter import file_converter
from .handlers.lineal_regresion import run_regression

bp = Blueprint("main", __name__)


# =========================
# convertir archivo
# =========================

@bp.route("/api/v1.0/converter_file", methods=["POST"])
def converter_file_route():
    if "file" not in request.files:
        return jsonify({
            "ok": False,
            "error": "No se recibió ningún archivo"
        }), 400

    file = request.files["file"]

    try:
        # =========================
        # paginación
        # =========================

        page = int(request.form.get("page", 1))

        page_size = int(
            request.form.get("page_size", 100)
        )

        # =========================
        # procesar archivo
        # =========================

        result = file_converter(
            file=file,
            page=page,
            page_size=page_size
        )

        status_code = 200 if result.get("ok") else 400

        return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# =========================
# limpiar NaN
# =========================

def clean_nan_values(obj):
    if isinstance(obj, float):
        if math.isnan(obj):
            return None

        if math.isinf(obj):
            return None

        return obj

    elif isinstance(obj, dict):
        return {
            k: clean_nan_values(v)
            for k, v in obj.items()
        }

    elif isinstance(obj, list):
        return [
            clean_nan_values(item)
            for item in obj
        ]

    return obj


# =========================
# regresión lineal
# =========================

@bp.route("/api/v1.0/regression", methods=["POST"])
def lineal_regression():
    payload = request.get_json()

    if (
        not payload
        or "data" not in payload
        or "columns" not in payload
        or "dependent" not in payload
    ):
        return jsonify({
            "ok": False,
            "error": (
                "Debe enviar "
                "'data', 'columns' y "
                "'dependent'"
            )
        }), 400

    result = run_regression(
        payload["data"],
        payload["columns"],
        payload["dependent"]
    )

    cleaned_result = clean_nan_values(result)

    return jsonify(cleaned_result), (
        200 if result.get("ok") else 400
    )


# =========================
# explicación llm
# =========================

@bp.route("/api/v1.0/llm", methods=["POST"])
def llm_explain():
    payload = request.get_json()

    if not payload or "result" not in payload:
        return jsonify({
            "ok": False,
            "error": "result requerido"
        }), 400

    response = llm_handler(
        payload["result"]
    )

    if not response:
        return jsonify({
            "ok": False,
            "error": "falló el modelo"
        }), 500

    try:
        response_clean = json.loads(
            f'"{response}"'
        ).replace("\\n", "\n")

    except Exception:
        response_clean = response

    return jsonify({
        "ok": True,
        "response": response_clean
    }), 200


# =========================
# health
# =========================

@bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "regresion-backend"
    }), 200