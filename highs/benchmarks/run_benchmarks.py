"""Benchmarks reproducibles del motor `highs`.

No son tests de CI: no usan umbrales universales de milisegundos. Registran
hardware, sistema operativo, versiones, opciones y datos de entrada para que
los resultados medidos sean comparables. Uso:

    python benchmarks/run_benchmarks.py [--repetitions 3] [--output benchmarks/results.md]
"""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from highs_api import __version__
from highs_api.config import settings
from highs_api.core.converters import engine_version
from highs_api.models.common import SolveResponse
from highs_api.models.lp import LPRequest
from highs_api.models.mip import MIPRequest
from highs_api.models.qp import QPRequest
from highs_api.solvers.lp_solver import solve_lp
from highs_api.solvers.mip_solver import solve_mip
from highs_api.solvers.qp_solver import solve_qp


@dataclass(frozen=True)
class Case:
    name: str
    description: str
    payload: object


def build_lp_case(n_variables: int = 100, n_constraints: int = 50, seed: int = 7) -> LPRequest:
    """LP de 100 variables y 50 restricciones con solución no trivial."""
    rng = np.random.default_rng(seed)
    costs = rng.uniform(1.0, 10.0, n_variables)
    constraints = []
    for _ in range(n_constraints):
        row = np.zeros(n_variables)
        chosen = rng.choice(n_variables, size=5, replace=False)
        row[chosen] = 0.01
        constraints.append({"coefficients": row.tolist(), "sense": "<=", "rhs": 0.5})
    constraints.append(
        {"coefficients": np.ones(n_variables).tolist(), "sense": "=", "rhs": n_variables / 2}
    )
    return LPRequest.model_validate(
        {
            "objective": {"sense": "minimize", "coefficients": costs.tolist()},
            "constraints": constraints,
            "bounds": [{"lower": 0, "upper": 1} for _ in range(n_variables)],
        }
    )


def build_mip_case(n_variables: int = 50, seed: int = 11) -> MIPRequest:
    """Mochila 0/1 con 50 binarias."""
    rng = np.random.default_rng(seed)
    values = rng.integers(1, 50, n_variables).astype(float)
    weights = rng.integers(1, 50, n_variables).astype(float)
    capacity = float(weights.sum() // 3)
    return MIPRequest.model_validate(
        {
            "objective": {"sense": "maximize", "coefficients": values.tolist()},
            "constraints": [{"coefficients": weights.tolist(), "sense": "<=", "rhs": capacity}],
            "integrality": ["binary"] * n_variables,
            "options": {"mip_rel_gap": 0, "time_limit": 60},
        }
    )


def build_qp_case(n_variables: int = 100, n_factors: int = 20, seed: int = 13) -> QPRequest:
    """QP PSD de 100 variables: Q = A^T A + 0.5 I, presupuesto suma = 1."""
    rng = np.random.default_rng(seed)
    factors = rng.normal(size=(n_factors, n_variables))
    matrix = factors.T @ factors + 0.5 * np.eye(n_variables)
    costs = rng.normal(size=n_variables)
    return QPRequest.model_validate(
        {
            "objective": {"sense": "minimize", "coefficients": costs.tolist()},
            "Q": matrix.round(6).tolist(),
            "constraints": [
                {"coefficients": np.ones(n_variables).tolist(), "sense": "=", "rhs": 1.0}
            ],
            "bounds": [{"lower": 0, "upper": 1} for _ in range(n_variables)],
            "options": {"time_limit": 60},
        }
    )


def _run_solver(case: Case) -> SolveResponse:
    if isinstance(case.payload, LPRequest):
        return solve_lp(case.payload)
    if isinstance(case.payload, MIPRequest):
        return solve_mip(case.payload)
    assert isinstance(case.payload, QPRequest)
    return solve_qp(case.payload)


def _format_environment() -> list[tuple[str, str]]:
    return [
        ("Fecha (UTC)", datetime.now(UTC).isoformat(timespec="seconds")),
        ("Sistema", platform.platform()),
        ("Máquina", platform.machine()),
        ("Procesador", platform.processor() or "desconocido"),
        ("CPUs", str(settings.max_threads)),
        ("Python", sys.version.split()[0]),
        ("highs-api", __version__),
        ("HiGHS (highspy)", engine_version()),
        ("Presolve", "choose"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmarks del motor highs")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results.md"))
    arguments = parser.parse_args()

    cases = [
        Case(
            "LP 100x50", "LP de 100 variables y 51 restricciones (densa en JSON)", build_lp_case()
        ),
        Case("MIP 50 binarias", "Mochila 0/1 con 50 binarias", build_mip_case()),
        Case("QP 100 variables", "QP convexo con Q = A^T A + 0.5 I", build_qp_case()),
    ]

    rows: list[str] = []
    for case in cases:
        wall_times: list[float] = []
        response: SolveResponse | None = None
        for _ in range(arguments.repetitions):
            started = time.perf_counter()
            response = _run_solver(case)
            wall_times.append((time.perf_counter() - started) * 1000.0)
        assert response is not None
        objective_text = (
            "null" if response.objective_value is None else f"{response.objective_value:.6g}"
        )
        solve_ms = response.metadata.solve_time_ms or 0.0
        rows.append(
            f"| {case.name} | {arguments.repetitions} | "
            f"{min(wall_times):.2f} | {statistics.median(wall_times):.2f} | "
            f"{solve_ms:.2f} | {response.status.value} | {objective_text} |"
        )
        print(f"{case.name}: min={min(wall_times):.2f} ms | status={response.status.value}")

    lines = [
        "# Benchmarks medidos del motor `highs`",
        "",
        "> Valores medidos en el entorno descrito abajo. Son objetivos registrados,",
        "> no garantías universales de latencia.",
        "",
        "## Entorno",
        "",
        "| Campo | Valor |",
        "|---|---|",
    ]
    lines += [f"| {key} | {value} |" for key, value in _format_environment()]
    lines += [
        "",
        "## Resultados",
        "",
        "| Caso | Repeticiones | Mejor wall (ms) | Mediana wall (ms) | solve_time_ms (motor) "
        "| Estado | Objetivo |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    lines += rows
    lines += [
        "",
        "Notas:",
        "",
        "- `wall` incluye validación, conversión a HiGHS y resolución; `solve_time_ms`",
        "  solo la llamada a `run()`.",
        "- Los datos de entrada son deterministas (semillas fijas) y se generan en",
        "  `benchmarks/run_benchmarks.py`; un cambio de semilla cambia el problema.",
        "- No se usan estos valores como umbral de CI compartida.",
        "",
    ]

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"reporte escrito en {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
