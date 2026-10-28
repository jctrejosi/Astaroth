use crate::model::{Employee, PlanRequest, Task, TaskStatus};

/// Capacidad efectiva de un empleado para un horizonte dado (en minutos).
///
/// Si el empleado tiene turnos definidos, se suma el tiempo de cada turno que
/// cae dentro del horizonte; si no, se usa la disponibilidad declarada
/// (`available_minutes`).
pub fn effective_capacity(employee: &Employee, horizon_minutes: u32) -> u32 {
    if employee.shifts.is_empty() {
        return employee.available_minutes;
    }
    employee
        .shifts
        .iter()
        .map(|s| {
            if s.start_minutes >= horizon_minutes {
                0
            } else {
                s.end_minutes
                    .min(horizon_minutes)
                    .saturating_sub(s.start_minutes)
            }
        })
        .sum()
}

/// Duración estimada de una tarea para un empleado.
///
/// Usa la estimación explícita si existe; en su ausencia (arranque en frío)
/// recurre a la media del equipo para esa tarea. Devuelve `None` si el empleado
/// no tiene la habilidad o si no hay ninguna estimación de la que partir.
pub fn duration_for(req: &PlanRequest, task: &Task, employee: &Employee) -> Option<u32> {
    if let Some(&d) = task.estimated_minutes_by_employee.get(&employee.id) {
        return Some(d);
    }
    if !employee.skills.iter().any(|s| *s == task.task_type) {
        return None;
    }
    let estimates: Vec<u32> = req
        .employees
        .iter()
        .filter(|e| e.skills.iter().any(|s| *s == task.task_type))
        .filter_map(|e| task.estimated_minutes_by_employee.get(&e.id))
        .copied()
        .collect();
    if estimates.is_empty() {
        return None;
    }
    let sum: u64 = estimates.iter().map(|&v| v as u64).sum();
    Some((sum / estimates.len() as u64) as u32)
}

/// Empleados elegibles para una tarea: tienen la habilidad y una duración
/// estimable (explícita o por media del equipo).
pub fn eligible_employees<'a>(req: &'a PlanRequest, task: &Task) -> Vec<&'a Employee> {
    req.employees
        .iter()
        .filter(|e| duration_for(req, task, e).is_some())
        .collect()
}

/// Duración mínima estimada entre empleados elegibles, si existe.
pub fn min_duration(req: &PlanRequest, task: &Task) -> Option<u32> {
    req.employees
        .iter()
        .filter_map(|e| duration_for(req, task, e))
        .min()
}

/// Tiempo restante de las tareas en ejecución asignadas a un empleado.
pub fn running_remaining(req: &PlanRequest, employee_id: &str) -> u32 {
    req.tasks
        .iter()
        .filter(|t| {
            t.status == TaskStatus::Running && t.employee_id.as_deref() == Some(employee_id)
        })
        .filter_map(|t| t.remaining_minutes)
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Employee, Options, Shift, Task, TaskStatus};

    fn req(employees: Vec<Employee>, task: Task) -> PlanRequest {
        PlanRequest {
            horizon_minutes: 480,
            employees,
            tasks: vec![task],
            options: Options::default(),
            ..Default::default()
        }
    }

    fn task(task_type: &str, estimates: &[(&str, u32)]) -> Task {
        Task {
            id: "T".into(),
            status: TaskStatus::Pending,
            task_type: task_type.into(),
            current_employee_id: None,
            employee_id: None,
            remaining_minutes: None,
            estimated_minutes_by_employee: estimates
                .iter()
                .map(|(id, d)| (id.to_string(), *d))
                .collect(),
            priority: 0,
            deadline_minutes: None,
            dependencies: vec![],
        }
    }

    fn employee(id: &str, skills: &[&str]) -> Employee {
        Employee {
            id: id.into(),
            available_minutes: 100,
            skills: skills.iter().map(|s| s.to_string()).collect(),
            shifts: vec![],
        }
    }

    #[test]
    fn la_capacidad_con_turnos_se_acota_al_horizonte() {
        let e = Employee {
            id: "E".into(),
            available_minutes: 0,
            skills: vec![],
            shifts: vec![
                Shift {
                    start_minutes: 0,
                    end_minutes: 120,
                },
                Shift {
                    start_minutes: 300,
                    end_minutes: 600,
                },
            ],
        };
        // Horizonte 400: turno 1 completo (120) + turno 2 parcial (400-300=100).
        assert_eq!(effective_capacity(&e, 400), 220);
    }

    #[test]
    fn sin_turnos_usa_la_disponibilidad() {
        let e = employee("E", &["x"]);
        assert_eq!(effective_capacity(&e, 480), 100);
    }

    #[test]
    fn el_fallback_usa_la_media_del_equipo() {
        let r = req(
            vec![
                employee("A", &["x"]),
                employee("B", &["x"]),
                employee("C", &["x"]),
            ],
            task("x", &[("A", 10), ("B", 20)]),
        );
        let c = r.employees.iter().find(|e| e.id == "C").unwrap();
        // C no tiene estimación explícita → media de A y B = 15.
        assert_eq!(duration_for(&r, &r.tasks[0], c), Some(15));
        // C es elegible gracias al fallback.
        assert_eq!(eligible_employees(&r, &r.tasks[0]).len(), 3);
    }

    #[test]
    fn sin_ninguna_estimacion_no_hay_fallback() {
        let r = req(vec![employee("A", &["x"])], task("x", &[]));
        assert!(eligible_employees(&r, &r.tasks[0]).is_empty());
    }
}
