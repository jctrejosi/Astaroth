use crate::capacity;
use crate::estimator;
use crate::model::{PlanRequest, PlanResponse, PlanStatus};
use crate::solver::Solution;

/// Compone la respuesta final a partir del resultado del solver, el análisis de
/// capacidad independiente y el estimador/forecast. El balanceador es stateless:
/// no persiste nada y solo combina los resultados de un único cálculo.
pub fn build_response(req: &PlanRequest, solution: Solution) -> PlanResponse {
    let analysis = capacity::analyze(req, &solution.assignments);

    // Fusiona las tareas sin asignación: las que el solver no pudo colocar y las
    // que el análisis de habilidades declara inasignables.
    let mut unassigned = solution.unassigned_tasks.clone();
    unassigned.extend(analysis.unassignable.iter().cloned());
    unassigned.sort();
    unassigned.dedup();

    // Advertencias agregadas desde el análisis de capacidad.
    let mut warnings = solution.warnings.clone();
    for s in &analysis.skill_shortages {
        warnings.push(format!(
            "SKILL_SHORTAGE: la habilidad {} requiere {} min y solo hay {} min disponibles (déficit {} min)",
            s.skill, s.required_minutes, s.available_minutes, s.shortage_minutes
        ));
    }
    for o in &analysis.overloaded {
        warnings.push(format!(
            "EMPLOYEE_OVERLOADED: {} tiene {} min de carga frente a {} min de capacidad",
            o.employee_id, o.workload_minutes, o.capacity_minutes
        ));
    }
    for task_id in &analysis.deadline_risks {
        warnings.push(format!(
            "DEADLINE_RISK: la tarea {task_id} excede su fecha límite proyectada"
        ));
    }

    let updated_estimates = estimator::updated_estimates(req);
    let demand_forecast =
        estimator::forecast_demand(&req.arrival_history, req.options.forecast_periods);

    let status = resolve_status(solution.status_hint, &analysis, &unassigned);

    PlanResponse {
        status,
        makespan_minutes: solution.makespan_minutes,
        assignments: solution.assignments,
        running_tasks_unchanged: solution.running_tasks_unchanged,
        changes: solution.changes,
        capacity: analysis.report,
        unassigned_tasks: unassigned,
        solver: solution.solver,
        warnings,
        updated_estimates,
        demand_forecast,
    }
}

/// Resuelve el estado global aplicando precedencia entre fuentes:
/// `UNASSIGNABLE` > `CAPACITY_SHORTAGE` > `UNKNOWN` > `FEASIBLE`.
fn resolve_status(
    hint: Option<PlanStatus>,
    analysis: &capacity::Analysis,
    unassigned: &[String],
) -> PlanStatus {
    let mut status = PlanStatus::Feasible;
    if let Some(h) = hint {
        status = worse(status, h);
    }
    if analysis.has_shortage() {
        status = worse(status, PlanStatus::CapacityShortage);
    }
    if !unassigned.is_empty() {
        status = worse(status, PlanStatus::Unassignable);
    }
    status
}

/// Devuelve el estado de mayor severidad entre dos estados.
fn worse(a: PlanStatus, b: PlanStatus) -> PlanStatus {
    fn rank(s: PlanStatus) -> u8 {
        match s {
            PlanStatus::Feasible => 0,
            PlanStatus::Unknown => 1,
            PlanStatus::CapacityShortage => 2,
            PlanStatus::Unassignable => 3,
        }
    }
    if rank(b) > rank(a) {
        b
    } else {
        a
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Assignment, SolverInfo};

    fn solution(status_hint: Option<PlanStatus>) -> Solution {
        Solution {
            makespan_minutes: Some(30),
            assignments: vec![],
            changes: vec![],
            running_tasks_unchanged: vec![],
            unassigned_tasks: vec![],
            solver: SolverInfo {
                method: "test".into(),
                optimality_proven: false,
            },
            warnings: vec![],
            status_hint,
        }
    }

    fn empty_req() -> PlanRequest {
        PlanRequest {
            horizon_minutes: 60,
            employees: vec![],
            tasks: vec![],
            options: Default::default(),
            ..Default::default()
        }
    }

    #[test]
    fn sin_datos_devuelve_factible() {
        let response = build_response(&empty_req(), solution(None));
        assert_eq!(response.status, PlanStatus::Feasible);
        assert_eq!(response.capacity.shortage_minutes, 0);
    }

    #[test]
    fn el_hint_unknown_predomina_sobre_factible() {
        let response = build_response(&empty_req(), solution(Some(PlanStatus::Unknown)));
        assert_eq!(response.status, PlanStatus::Unknown);
    }

    #[test]
    fn unassigned_domina_sobre_el_resto() {
        let mut sol = solution(Some(PlanStatus::CapacityShortage));
        sol.unassigned_tasks = vec!["T1".into()];
        let response = build_response(&empty_req(), sol);
        assert_eq!(response.status, PlanStatus::Unassignable);
    }

    #[test]
    fn capacidad_insuficiente_se_refleja_en_el_estado() {
        use crate::model::{Employee, Options, Task, TaskStatus};
        let req = PlanRequest {
            horizon_minutes: 480,
            employees: vec![Employee {
                id: "E1".into(),
                available_minutes: 10,
                skills: vec!["packing".into()],
                shifts: vec![],
            }],
            tasks: vec![Task {
                id: "T1".into(),
                status: TaskStatus::Pending,
                task_type: "packing".into(),
                current_employee_id: None,
                employee_id: None,
                remaining_minutes: None,
                estimated_minutes_by_employee: [("E1".into(), 20)].into_iter().collect(),
                priority: 0,
                deadline_minutes: None,
                dependencies: vec![],
            }],
            options: Options::default(),
            ..Default::default()
        };
        let mut sol = solution(None);
        sol.assignments = vec![Assignment {
            task_id: "T1".into(),
            employee_id: "E1".into(),
        }];
        let response = build_response(&req, sol);
        assert_eq!(response.status, PlanStatus::CapacityShortage);
        assert!(response
            .warnings
            .iter()
            .any(|w| w.contains("SKILL_SHORTAGE")));
        assert!(response
            .warnings
            .iter()
            .any(|w| w.contains("EMPLOYEE_OVERLOADED")));
    }

    #[test]
    fn el_capacity_report_viene_del_analisis() {
        let response = build_response(&empty_req(), solution(None));
        assert_eq!(response.capacity.required_minutes, 0);
        assert_eq!(response.capacity.available_minutes, 0);
        assert_eq!(response.capacity.shortage_minutes, 0);
    }

    #[test]
    fn propaga_estimaciones_y_forecast_a_la_respuesta() {
        use crate::model::{DurationObservation, Options};
        let req = PlanRequest {
            horizon_minutes: 60,
            employees: vec![],
            tasks: vec![],
            options: Options {
                ema_alpha: 0.5,
                forecast_periods: 2,
                ..Default::default()
            },
            duration_observations: vec![DurationObservation {
                employee_id: "E1".into(),
                task_type: "packing".into(),
                actual_minutes: 30,
            }],
            arrival_history: vec![4, 6],
        };
        let response = build_response(&req, solution(None));
        assert_eq!(response.updated_estimates.len(), 1);
        assert_eq!(response.updated_estimates[0].duration_minutes, 30);
        assert_eq!(response.demand_forecast, vec![5, 5]);
    }
}
