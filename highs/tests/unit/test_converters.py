"""Conversiones a HiGHS: estados, restricciones, cotas, integralidad y Hessiana."""

from __future__ import annotations

import math

import highspy
import pytest

from highs_api.core.converters import (
    build_message,
    constraint_row_bounds,
    create_engine,
    finite_or_none,
    finite_vector_or_none,
    hessian_csc,
    integrality_arrays,
    map_status,
    require_status,
    set_engine_option,
)
from highs_api.core.exceptions import SolverExecutionError
from highs_api.core.validators import resolve_bounds
from highs_api.models.common import Bound, Constraint, ConstraintSense, SolverStatus, VariableType

# Cobertura total del enum de la versión fijada: cada miembro tiene destino
# explícito (estado público) o se convierte en un error controlado.
_EXPECTED_STATUS = {
    "kNotset": SolverStatus.unknown,
    "kModelEmpty": SolverStatus.unknown,
    "kOptimal": SolverStatus.optimal,
    "kInfeasible": SolverStatus.infeasible,
    "kUnboundedOrInfeasible": SolverStatus.unbounded_or_infeasible,
    "kUnbounded": SolverStatus.unbounded,
    "kObjectiveBound": SolverStatus.objective_bound,
    "kObjectiveTarget": SolverStatus.objective_target,
    "kTimeLimit": SolverStatus.time_limit,
    "kIterationLimit": SolverStatus.iteration_limit,
    "kSolutionLimit": SolverStatus.solution_limit,
    "kInterrupt": SolverStatus.interrupted,
    "kHighsInterrupt": SolverStatus.interrupted,
    "kMemoryLimit": SolverStatus.memory_limit,
    "kUnknown": SolverStatus.unknown,
}

_ERROR_STATUS = {"kLoadError", "kModelError", "kPresolveError", "kSolveError", "kPostsolveError"}


def test_todos_los_estados_del_enum_estan_cubiertos_explicitamente() -> None:
    members = dict(highspy.HighsModelStatus.__members__)
    assert set(members) <= set(_EXPECTED_STATUS) | _ERROR_STATUS

    for name, member in members.items():
        if name in _ERROR_STATUS:
            with pytest.raises(SolverExecutionError):
                map_status(member)
        else:
            assert map_status(member) is _EXPECTED_STATUS[name]


def test_require_status_detecta_errores_del_motor() -> None:
    require_status(highspy.HighsStatus.kOk, "prueba")
    require_status(highspy.HighsStatus.kWarning, "prueba")

    with pytest.raises(SolverExecutionError):
        require_status(highspy.HighsStatus.kError, "prueba")


def test_set_engine_option_desconocida_lanza_solver_error() -> None:
    engine = create_engine()
    with pytest.raises(SolverExecutionError):
        set_engine_option(engine, "opcion_que_no_existe_en_highs", 1)


def test_conversion_de_sentidos_a_limites_de_fila() -> None:
    le = Constraint(coefficients=[1.0], sense=ConstraintSense.le, rhs=4.0)
    ge = Constraint(coefficients=[1.0], sense=ConstraintSense.ge, rhs=4.0)
    eq = Constraint(coefficients=[1.0], sense=ConstraintSense.eq, rhs=4.0)

    assert constraint_row_bounds(le) == (-math.inf, 4.0)
    assert constraint_row_bounds(ge) == (4.0, math.inf)
    assert constraint_row_bounds(eq) == (4.0, 4.0)


def test_cotas_ausentes_finitas_e_ilimitadas() -> None:
    lowers, uppers = resolve_bounds(None, 2)
    assert lowers == [0.0, 0.0]
    assert uppers == [math.inf, math.inf]

    bounds = [
        Bound(lower=None, upper=None),
        Bound(lower=2.0, upper=3.0),
    ]
    lowers, uppers = resolve_bounds(bounds, 2)
    assert lowers == [-math.inf, 2.0]
    assert uppers == [math.inf, 3.0]

    # lower omitido vale 0; upper omitido vale +inf.
    bounds = [Bound(), Bound()]
    lowers, uppers = resolve_bounds(bounds, 2)
    assert lowers == [0.0, 0.0]
    assert uppers == [math.inf, math.inf]


def test_conversion_de_integralidad() -> None:
    indices, kinds = integrality_arrays(
        [VariableType.continuous, VariableType.binary, VariableType.integer]
    )
    assert indices == [1, 2]
    assert kinds == [highspy.HighsVarType.kInteger, highspy.HighsVarType.kInteger]

    indices, kinds = integrality_arrays([VariableType.continuous])
    assert indices == []
    assert kinds == []


def test_hessiana_csc_para_matriz_3x3_conocida() -> None:
    matrix = [
        [4.0, 1.0, 0.0],
        [1.0, 3.0, 2.0],
        [0.0, 2.0, 5.0],
    ]
    start, index, value = hessian_csc(matrix)

    # Solo la mitad triangular inferior, columna a columna, sin ceros.
    assert start == [0, 2, 4, 5]
    assert index == [0, 1, 1, 2, 2]
    assert value == [4.0, 1.0, 3.0, 2.0, 5.0]
    assert len(value) == 5
    assert all(0 <= i < 3 for i in index)
    assert all(start[i] <= start[i + 1] for i in range(len(start) - 1))


def test_hessiana_cero_no_aporta_elementos() -> None:
    start, index, value = hessian_csc([[0.0, 0.0], [0.0, 0.0]])
    assert start == [0, 0, 0]
    assert index == []
    assert value == []


def test_valores_no_finitos_nunca_pasan_al_contrato() -> None:
    assert finite_or_none(math.inf) is None
    assert finite_or_none(-math.inf) is None
    assert finite_or_none(math.nan) is None
    assert finite_or_none(2.5) == 2.5
    assert finite_or_none(None) is None

    assert finite_vector_or_none([1.0, math.inf]) is None
    assert finite_vector_or_none([math.nan, 0.0]) is None
    assert finite_vector_or_none([1.0, 2.0]) == [1.0, 2.0]
    assert finite_vector_or_none([]) == []


def test_mensaje_de_limite_con_solucion_disponible() -> None:
    assert build_message(SolverStatus.optimal, True) is None

    message = build_message(SolverStatus.time_limit, True)
    assert message is not None
    assert "límite de tiempo" in message
    assert "mejor solución factible" in message

    message = build_message(SolverStatus.time_limit, False)
    assert message is not None
    assert "mejor solución factible" not in message

    assert build_message(SolverStatus.infeasible, False) == "El modelo es infactible."
