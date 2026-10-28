use std::collections::BTreeMap;

use crate::domain;
use crate::highs::{HighsConstraint, HighsMipOptions, HighsMipRequest, HighsObjective};
use crate::model::{PlanRequest, TaskStatus};

/// Modelo MIP del problema de asignación, listo para enviar a HiGHS.
///
/// Nota: este modelo cubre asignación + makespan + capacidad. Las dependencias
/// entre tareas (secuenciación) las resuelve el solver heurístico; modelarlas en
/// MIP requeriría variables de tiempo de inicio adicionales.
pub struct AssignmentMip {
    pub request: HighsMipRequest,
    /// `var_map[idx] = Some((employee_id, task_id))` para cada `x_ij`;
    /// `None` para la variable de makespan (última).
    pub var_map: Vec<Option<(String, String)>>,
}

pub fn build_assignment_mip(req: &PlanRequest, time_limit: Option<f64>) -> AssignmentMip {
    let mut var_map: Vec<(String, String)> = Vec::new();
    let mut var_index: BTreeMap<(String, String), usize> = BTreeMap::new();

    let pending: Vec<_> = req
        .tasks
        .iter()
        .filter(|t| matches!(t.status, TaskStatus::Pending | TaskStatus::Assigned))
        .collect();

    for task in &pending {
        for employee in &req.employees {
            if domain::duration_for(req, task, employee).is_some() {
                let idx = var_map.len();
                var_map.push((employee.id.clone(), task.id.clone()));
                var_index.insert((employee.id.clone(), task.id.clone()), idx);
            }
        }
    }

    let makespan_idx = var_map.len();
    let n = makespan_idx + 1;

    let mut coeffs = vec![0.0; n];
    coeffs[makespan_idx] = 1.0;
    let objective = HighsObjective {
        sense: "minimize".to_string(),
        coefficients: coeffs,
    };

    let mut constraints = Vec::new();

    // (1) Asignación única: sum_i x_ij = 1.
    for task in &pending {
        let mut c = vec![0.0; n];
        let mut any = false;
        for employee in &req.employees {
            if let Some(&idx) = var_index.get(&(employee.id.clone(), task.id.clone())) {
                c[idx] = 1.0;
                any = true;
            }
        }
        if any {
            constraints.push(HighsConstraint {
                coefficients: c,
                sense: "=".to_string(),
                rhs: 1.0,
            });
        }
    }

    // (2) Makespan: r_i + sum_j p_ij x_ij <= M  →  sum p x - M <= -r_i.
    for employee in &req.employees {
        let r_i = domain::running_remaining(req, &employee.id) as f64;
        let mut c = vec![0.0; n];
        let mut any = false;
        for task in &pending {
            if let Some(&idx) = var_index.get(&(employee.id.clone(), task.id.clone())) {
                c[idx] = domain::duration_for(req, task, employee).unwrap() as f64;
                any = true;
            }
        }
        c[makespan_idx] = -1.0;
        if any || r_i > 0.0 {
            constraints.push(HighsConstraint {
                coefficients: c,
                sense: "<=".to_string(),
                rhs: -r_i,
            });
        }
    }

    // (3) Capacidad (opcional): r_i + sum_j p_ij x_ij <= C_i(H).
    if req.options.enforce_capacity {
        for employee in &req.employees {
            let r_i = domain::running_remaining(req, &employee.id) as f64;
            let capacity = domain::effective_capacity(employee, req.horizon_minutes) as f64;
            let mut c = vec![0.0; n];
            let mut any = false;
            for task in &pending {
                if let Some(&idx) = var_index.get(&(employee.id.clone(), task.id.clone())) {
                    c[idx] = domain::duration_for(req, task, employee).unwrap() as f64;
                    any = true;
                }
            }
            if any {
                constraints.push(HighsConstraint {
                    coefficients: c,
                    sense: "<=".to_string(),
                    rhs: (capacity - r_i).max(0.0),
                });
            }
        }
    }

    let mut integrality = vec!["binary".to_string(); makespan_idx];
    integrality.push("continuous".to_string());

    let var_map = var_map
        .into_iter()
        .map(Some)
        .chain(std::iter::once(None))
        .collect();

    AssignmentMip {
        request: HighsMipRequest {
            objective,
            constraints,
            bounds: None,
            integrality,
            options: Some(HighsMipOptions {
                time_limit,
                mip_rel_gap: None,
            }),
        },
        var_map,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Employee, Options, Task};

    #[test]
    fn construye_el_mip_con_asignacion_makespan_y_capacidad() {
        let req = PlanRequest {
            horizon_minutes: 480,
            employees: vec![Employee {
                id: "E1".into(),
                available_minutes: 100,
                skills: vec!["x".into()],
                shifts: vec![],
            }],
            tasks: vec![Task {
                id: "T1".into(),
                status: TaskStatus::Pending,
                task_type: "x".into(),
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

        let mip = build_assignment_mip(&req, None);

        // var_map: [Some((E1, T1)), None(makespan)]
        assert_eq!(mip.var_map.len(), 2);
        assert_eq!(mip.var_map[0], Some(("E1".to_string(), "T1".to_string())));
        assert_eq!(mip.var_map[1], None);

        // Objetivo: minimizar M (coeficiente 1 en la última variable).
        assert_eq!(mip.request.objective.coefficients, vec![0.0, 1.0]);
        assert_eq!(mip.request.objective.sense, "minimize");

        // Restricciones: asignación única + makespan + capacidad (enforce por defecto).
        assert_eq!(mip.request.constraints.len(), 3);
        assert_eq!(mip.request.constraints[0].sense, "=");
        assert_eq!(mip.request.constraints[0].rhs, 1.0);
        // Capacidad: r_i + 20 <= 100.
        assert_eq!(mip.request.constraints[2].rhs, 100.0);

        assert_eq!(mip.request.integrality, vec!["binary", "continuous"]);
    }
}
