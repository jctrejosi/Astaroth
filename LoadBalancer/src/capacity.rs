use std::collections::{BTreeMap, BTreeSet};

use crate::domain;
use crate::model::{Assignment, CapacityReport, PlanRequest, Task, TaskStatus};

#[derive(Debug, Clone)]
pub struct Analysis {
    pub report: CapacityReport,
    pub unassignable: Vec<String>,
    pub skill_shortages: Vec<SkillShortage>,
    pub deadline_risks: Vec<String>,
    pub overloaded: Vec<Overload>,
}

#[derive(Debug, Clone)]
pub struct SkillShortage {
    pub skill: String,
    pub required_minutes: u32,
    pub available_minutes: u32,
    pub shortage_minutes: u32,
}

#[derive(Debug, Clone)]
pub struct Overload {
    pub employee_id: String,
    pub workload_minutes: u32,
    pub capacity_minutes: u32,
}

impl Analysis {
    pub fn has_shortage(&self) -> bool {
        self.report.shortage_minutes > 0
            || self.skill_shortages.iter().any(|s| s.shortage_minutes > 0)
            || !self.overloaded.is_empty()
    }
}

/// Análisis completo de capacidad: déficit agregado, por habilidad, sobrecarga
/// por empleado, tareas sin asignación posible y riesgo de plazo.
pub fn analyze(req: &PlanRequest, assignments: &[Assignment]) -> Analysis {
    Analysis {
        report: assess(req),
        unassignable: find_unassignable(req),
        skill_shortages: skill_shortages(req),
        deadline_risks: deadline_risks(req, assignments),
        overloaded: overloads(req, assignments),
    }
}

/// Demanda, capacidad efectiva y déficit agregado.
pub fn assess(req: &PlanRequest) -> CapacityReport {
    let mut required: u64 = 0;
    for task in &req.tasks {
        match task.status {
            TaskStatus::Running => required += task.remaining_minutes.unwrap_or(0) as u64,
            TaskStatus::Pending | TaskStatus::Assigned => {
                if let Some(min) = domain::min_duration(req, task) {
                    required += min as u64;
                }
            }
        }
    }

    let available: u64 = req
        .employees
        .iter()
        .map(|e| domain::effective_capacity(e, req.horizon_minutes) as u64)
        .sum();
    let shortage = required.saturating_sub(available);

    CapacityReport {
        required_minutes: cap(required),
        available_minutes: cap(available),
        shortage_minutes: cap(shortage),
    }
}

/// Tareas planificables sin ningún empleado elegible.
fn find_unassignable(req: &PlanRequest) -> Vec<String> {
    let mut out = Vec::new();
    for task in req.tasks.iter().filter(|t| t.is_plannable()) {
        if domain::eligible_employees(req, task).is_empty() {
            out.push(task.id.clone());
        }
    }
    out
}

/// Déficit por habilidad: el agregado no detecta restricciones de skills.
fn skill_shortages(req: &PlanRequest) -> Vec<SkillShortage> {
    let mut skills: BTreeSet<&str> = BTreeSet::new();
    for task in req.tasks.iter().filter(|t| t.is_plannable()) {
        skills.insert(task.task_type.as_str());
    }

    let mut out = Vec::new();
    for skill in skills {
        let mut required: u64 = 0;
        for task in req
            .tasks
            .iter()
            .filter(|t| t.is_plannable() && t.task_type == skill)
        {
            // Mejor caso: mínima duración entre empleados con esta skill.
            let best = req
                .employees
                .iter()
                .filter(|e| e.skills.iter().any(|s| s == skill))
                .filter_map(|e| domain::duration_for(req, task, e))
                .min();
            if let Some(b) = best {
                required += b as u64;
            }
        }

        let available: u64 = req
            .employees
            .iter()
            .filter(|e| e.skills.iter().any(|s| s == skill))
            .map(|e| domain::effective_capacity(e, req.horizon_minutes) as u64)
            .sum();

        let shortage = required.saturating_sub(available);
        if shortage > 0 {
            out.push(SkillShortage {
                skill: skill.to_string(),
                required_minutes: cap(required),
                available_minutes: cap(available),
                shortage_minutes: cap(shortage),
            });
        }
    }
    out
}

/// Riesgo de plazo: con el plan propuesto, el fin proyectado supera el `deadline`.
fn deadline_risks(req: &PlanRequest, assignments: &[Assignment]) -> Vec<String> {
    let mut by_employee: BTreeMap<&str, Vec<(&Task, u32)>> = BTreeMap::new();
    for assignment in assignments {
        if let Some(task) = req.tasks.iter().find(|t| t.id == assignment.task_id) {
            if let Some(employee) = req
                .employees
                .iter()
                .find(|e| e.id == assignment.employee_id)
            {
                if let Some(duration) = domain::duration_for(req, task, employee) {
                    by_employee
                        .entry(assignment.employee_id.as_str())
                        .or_default()
                        .push((task, duration));
                }
            }
        }
    }

    let mut risks = Vec::new();
    for employee in &req.employees {
        let mut clock = domain::running_remaining(req, &employee.id) as u64;
        let mut queue = by_employee
            .get(employee.id.as_str())
            .cloned()
            .unwrap_or_default();
        // Orden de ejecución: prioridad descendente y, a igual prioridad, deadline.
        queue.sort_by(|a, b| {
            b.0.priority
                .cmp(&a.0.priority)
                .then_with(|| a.0.deadline_minutes.cmp(&b.0.deadline_minutes))
        });
        for (task, duration) in queue {
            clock += duration as u64;
            if let Some(deadline) = task.deadline_minutes {
                if clock > deadline as u64 {
                    risks.push(task.id.clone());
                }
            }
        }
    }

    risks.sort();
    risks.dedup();
    risks
}

/// Sobrecarga por empleado: carga asignada (en ejecución + planificada) que
/// supera la capacidad efectiva.
fn overloads(req: &PlanRequest, assignments: &[Assignment]) -> Vec<Overload> {
    let mut workload: BTreeMap<&str, u64> = BTreeMap::new();
    for employee in &req.employees {
        let r = domain::running_remaining(req, &employee.id) as u64;
        *workload.entry(employee.id.as_str()).or_insert(0) += r;
    }
    for assignment in assignments {
        if let (Some(task), Some(employee)) = (
            req.tasks.iter().find(|t| t.id == assignment.task_id),
            req.employees
                .iter()
                .find(|e| e.id == assignment.employee_id),
        ) {
            if let Some(d) = domain::duration_for(req, task, employee) {
                *workload.entry(assignment.employee_id.as_str()).or_insert(0) += d as u64;
            }
        }
    }

    let mut out = Vec::new();
    for employee in &req.employees {
        let capacity = domain::effective_capacity(employee, req.horizon_minutes) as u64;
        let wl = workload.get(employee.id.as_str()).copied().unwrap_or(0);
        if wl > capacity {
            out.push(Overload {
                employee_id: employee.id.clone(),
                workload_minutes: cap(wl),
                capacity_minutes: cap(capacity),
            });
        }
    }
    out.sort_by(|a, b| a.employee_id.cmp(&b.employee_id));
    out
}

fn cap(value: u64) -> u32 {
    value.min(u32::MAX as u64) as u32
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Employee, Options, Shift, Task};

    fn req() -> PlanRequest {
        PlanRequest {
            horizon_minutes: 480,
            employees: vec![
                Employee {
                    id: "E1".into(),
                    available_minutes: 10,
                    skills: vec!["packing".into()],
                    shifts: vec![],
                },
                Employee {
                    id: "E2".into(),
                    available_minutes: 100,
                    skills: vec!["labeling".into()],
                    shifts: vec![],
                },
            ],
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
        }
    }

    #[test]
    fn detecta_deficit_por_habilidad() {
        let analysis = analyze(&req(), &[]);
        // Agregado: 20 requeridas vs 110 disponibles → sin déficit.
        assert_eq!(analysis.report.shortage_minutes, 0);
        // Por habilidad: packing requiere 20 y solo E1 tiene 10 → déficit 10.
        let packing = analysis
            .skill_shortages
            .iter()
            .find(|s| s.skill == "packing")
            .unwrap();
        assert_eq!(packing.shortage_minutes, 10);
        assert!(analysis.has_shortage());
    }

    #[test]
    fn detecta_inasignable() {
        let mut r = req();
        r.tasks[0].estimated_minutes_by_employee.clear();
        let analysis = analyze(&r, &[]);
        assert_eq!(analysis.unassignable, vec!["T1"]);
    }

    #[test]
    fn la_capacidad_con_turnos_reduce_el_deficit() {
        let mut r = req();
        // E1 pasa de 10 a 300 minutos gracias a un turno.
        r.employees[0].shifts = vec![Shift {
            start_minutes: 0,
            end_minutes: 300,
        }];
        let analysis = analyze(&r, &[]);
        assert_eq!(analysis.report.available_minutes, 400); // 300 + 100
        assert_eq!(analysis.report.shortage_minutes, 0);
        assert!(!analysis.has_shortage());
    }

    #[test]
    fn detecta_sobrecarga_por_empleado() {
        let mut r = req();
        // T1 → E1 (20) supera la capacidad de E1 (10).
        r.tasks[0].estimated_minutes_by_employee = [("E1".into(), 20)].into_iter().collect();
        let analysis = analyze(
            &r,
            &[Assignment {
                task_id: "T1".into(),
                employee_id: "E1".into(),
            }],
        );
        assert_eq!(analysis.overloaded.len(), 1);
        assert_eq!(analysis.overloaded[0].employee_id, "E1");
        assert!(analysis.has_shortage());
    }
}
