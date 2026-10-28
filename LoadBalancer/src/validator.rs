use std::collections::{HashMap, HashSet};

use crate::error::ApiError;
use crate::model::PlanRequest;

pub fn validate(req: &PlanRequest) -> Result<(), ApiError> {
    let mut employee_ids: HashSet<&str> = HashSet::new();
    for e in &req.employees {
        if e.id.trim().is_empty() {
            return Err(bad("employee.id no puede estar vacío"));
        }
        if !employee_ids.insert(e.id.as_str()) {
            return Err(bad(format!("employee.id duplicado: {}", e.id)));
        }
        for shift in &e.shifts {
            if shift.start_minutes > shift.end_minutes {
                return Err(bad(format!("shift inválido para {} (start > end)", e.id)));
            }
        }
    }

    let mut task_ids: HashSet<&str> = HashSet::new();
    for t in &req.tasks {
        if t.id.trim().is_empty() {
            return Err(bad("task.id no puede estar vacío"));
        }
        if !task_ids.insert(t.id.as_str()) {
            return Err(bad(format!("task.id duplicado: {}", t.id)));
        }
    }

    for t in &req.tasks {
        if t.is_running() {
            let employee_id = t
                .employee_id
                .as_deref()
                .ok_or_else(|| bad(format!("task running sin employee_id: {}", t.id)))?;
            if !employee_ids.contains(employee_id) {
                return Err(bad(format!(
                    "task running referencia employee_id desconocido: {}",
                    t.id
                )));
            }
            if t.remaining_minutes.is_none() {
                return Err(bad(format!("task running sin remaining_minutes: {}", t.id)));
            }
        }

        if let Some(eid) = t.current_employee_id.as_deref() {
            if !employee_ids.contains(eid) {
                return Err(bad(format!(
                    "task {} referencia current_employee_id desconocido: {}",
                    t.id, eid
                )));
            }
        }

        for dep in &t.dependencies {
            if dep == &t.id {
                return Err(bad(format!("dependencia cíclica propia: {}", t.id)));
            }
            if !task_ids.contains(dep.as_str()) {
                return Err(bad(format!(
                    "task {} referencia dependencia desconocida: {}",
                    t.id, dep
                )));
            }
        }

        for eid in t.estimated_minutes_by_employee.keys() {
            if !employee_ids.contains(eid.as_str()) {
                return Err(bad(format!(
                    "task {} referencia empleado desconocido en la estimación: {}",
                    t.id, eid
                )));
            }
        }
    }

    detect_dependency_cycles(req)?;

    Ok(())
}

/// Detección de ciclos en el grafo de dependencias (DFS con colores).
fn detect_dependency_cycles(req: &PlanRequest) -> Result<(), ApiError> {
    let graph: HashMap<&str, &[String]> = req
        .tasks
        .iter()
        .map(|t| (t.id.as_str(), t.dependencies.as_slice()))
        .collect();

    #[derive(Clone, Copy, PartialEq)]
    enum Mark {
        Unvisited,
        Visiting,
        Done,
    }

    let mut marks: HashMap<&str, Mark> = req
        .tasks
        .iter()
        .map(|t| (t.id.as_str(), Mark::Unvisited))
        .collect();

    fn visit<'a>(
        node: &'a str,
        graph: &HashMap<&'a str, &'a [String]>,
        marks: &mut HashMap<&'a str, Mark>,
    ) -> Result<(), String> {
        match marks.get(node) {
            Some(Mark::Visiting) => return Err(node.to_string()),
            Some(Mark::Done) => return Ok(()),
            _ => {}
        }
        marks.insert(node, Mark::Visiting);
        if let Some(deps) = graph.get(node) {
            for dep in *deps {
                visit(dep.as_str(), graph, marks).map_err(|cycle| {
                    if cycle == node {
                        format!("{} -> {}", node, dep)
                    } else {
                        cycle
                    }
                })?;
            }
        }
        marks.insert(node, Mark::Done);
        Ok(())
    }

    for node in graph.keys() {
        if let Err(cycle) = visit(node, &graph, &mut marks) {
            return Err(bad(format!("ciclo de dependencias detectado: {cycle}")));
        }
    }

    Ok(())
}

fn bad(message: impl Into<String>) -> ApiError {
    ApiError::BadRequest(message.into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Options, Task, TaskStatus};

    #[test]
    fn detecta_ciclo_entre_dos_tareas() {
        let req = PlanRequest {
            horizon_minutes: 100,
            employees: vec![],
            tasks: vec![
                Task {
                    id: "A".into(),
                    status: TaskStatus::Pending,
                    task_type: "x".into(),
                    current_employee_id: None,
                    employee_id: None,
                    remaining_minutes: None,
                    estimated_minutes_by_employee: Default::default(),
                    priority: 0,
                    deadline_minutes: None,
                    dependencies: vec!["B".into()],
                },
                Task {
                    id: "B".into(),
                    status: TaskStatus::Pending,
                    task_type: "x".into(),
                    current_employee_id: None,
                    employee_id: None,
                    remaining_minutes: None,
                    estimated_minutes_by_employee: Default::default(),
                    priority: 0,
                    deadline_minutes: None,
                    dependencies: vec!["A".into()],
                },
            ],
            options: Options::default(),
            ..Default::default()
        };
        assert!(validate(&req).is_err());
    }
}
