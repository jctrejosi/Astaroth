use std::collections::{BTreeMap, BTreeSet};

use crate::domain;
use crate::error::ApiError;
use crate::model::{Assignment, Change, PlanRequest, SolverInfo, Task};

/// Resultado de un motor de planificación, sin estado de capacidad (eso lo
/// calcula el orquestador de forma independiente).
#[derive(Debug, Clone, Default)]
pub struct Solution {
    pub makespan_minutes: Option<u32>,
    pub assignments: Vec<Assignment>,
    pub changes: Vec<Change>,
    pub running_tasks_unchanged: Vec<String>,
    pub unassigned_tasks: Vec<String>,
    pub solver: SolverInfo,
    pub warnings: Vec<String>,
    /// Estado sugerido por el solver (p. ej. HiGHS `infeasible`/`time_limit`).
    pub status_hint: Option<crate::model::PlanStatus>,
}

/// Abstracción del motor de planificación.
pub trait Solver: Send + Sync {
    fn method(&self) -> &'static str;
    async fn solve(&self, req: &PlanRequest) -> Result<Solution, ApiError>;
}

/// Asignación por lista (respeta dependencias) + búsqueda local (movimientos e
/// intercambios) sujeta a un umbral de mejora, con preferencia suave por no
/// superar la capacidad de cada empleado.
#[derive(Default)]
pub struct HeuristicSolver;

impl Solver for HeuristicSolver {
    fn method(&self) -> &'static str {
        "greedy_local_search"
    }

    async fn solve(&self, req: &PlanRequest) -> Result<Solution, ApiError> {
        let running: Vec<String> = req
            .tasks
            .iter()
            .filter(|t| t.is_running())
            .map(|t| t.id.clone())
            .collect();

        let (assignment, unassigned, warnings, workload, dep_makespan) = list_schedule(req);
        let has_deps = has_dependencies(req);

        // La búsqueda local usa un modelo de carga exacto solo sin dependencias.
        let (assignment, workload) = if has_deps {
            (assignment, workload)
        } else {
            local_search(req, assignment, workload)
        };

        let makespan = if has_deps {
            dep_makespan
        } else {
            makespan(&workload)
        };

        let changes = diff_changes(req, &assignment);

        Ok(Solution {
            makespan_minutes: Some(makespan),
            assignments: assignment
                .into_iter()
                .map(|(task_id, employee_id)| Assignment {
                    task_id,
                    employee_id,
                })
                .collect(),
            changes,
            running_tasks_unchanged: running,
            unassigned_tasks: unassigned,
            solver: SolverInfo {
                method: self.method().to_string(),
                optimality_proven: false,
            },
            warnings,
            status_hint: None,
        })
    }
}

/// Asignación por lista (list scheduling) que respeta dependencias: una tarea
/// solo se planifica cuando todas sus dependencias tienen tiempo de finalización
/// conocido. Devuelve asignación, tareas sin asignar, avisos, carga por empleado
/// y el makespan proyectado (que, con dependencias, puede superar la suma de
/// cargas por los tiempos muertos de espera).
fn list_schedule(
    req: &PlanRequest,
) -> (
    BTreeMap<String, String>,
    Vec<String>,
    Vec<String>,
    BTreeMap<String, u32>,
    u32,
) {
    let horizon = req.horizon_minutes;
    let enforce = req.options.enforce_capacity;

    let mut completion: BTreeMap<String, u32> = BTreeMap::new();
    let mut clock: BTreeMap<String, u32> = BTreeMap::new();
    let mut workload: BTreeMap<String, u32> = BTreeMap::new();

    for task in &req.tasks {
        if task.is_running() {
            if let (Some(eid), Some(rem)) = (&task.employee_id, task.remaining_minutes) {
                completion.insert(task.id.clone(), rem);
                *clock.entry(eid.clone()).or_insert(0) += rem;
                *workload.entry(eid.clone()).or_insert(0) += rem;
            }
        }
    }

    let plannable: Vec<&Task> = req.tasks.iter().filter(|t| t.is_plannable()).collect();
    let mut processed: BTreeSet<String> = BTreeSet::new();
    let mut assignment: BTreeMap<String, String> = BTreeMap::new();
    let mut unassigned: Vec<String> = Vec::new();
    let mut warnings: Vec<String> = Vec::new();

    loop {
        let ready: Vec<&Task> = plannable
            .iter()
            .filter(|t| !processed.contains(&t.id))
            .filter(|t| t.dependencies.iter().all(|d| completion.contains_key(d)))
            .copied()
            .collect();

        if ready.is_empty() {
            break;
        }

        let task = ready
            .into_iter()
            .min_by(|a, b| {
                scarcity(a, req)
                    .cmp(&scarcity(b, req))
                    .then_with(|| b.priority.cmp(&a.priority))
                    .then_with(|| a.deadline_minutes.cmp(&b.deadline_minutes))
                    .then_with(|| domain::min_duration(req, b).cmp(&domain::min_duration(req, a)))
            })
            .expect("ready no vacío");

        // La tarea no puede empezar antes de que terminen sus dependencias.
        let dep_ready = task
            .dependencies
            .iter()
            .filter_map(|d| completion.get(d))
            .copied()
            .max()
            .unwrap_or(0);

        let mut best: Option<(String, u32, u64)> = None;
        for employee in domain::eligible_employees(req, task) {
            let duration = domain::duration_for(req, task, employee).expect("elegible");
            let start = clock.get(&employee.id).copied().unwrap_or(0).max(dep_ready);
            let finish = start + duration;

            // Preferencia suave por no superar la capacidad (solo si se exige).
            let wl = workload.get(&employee.id).copied().unwrap_or(0);
            let overflow = if enforce {
                (wl + duration).saturating_sub(domain::effective_capacity(employee, horizon))
            } else {
                0
            };
            let score = finish as u64 + overflow as u64 * 1_000_000;

            let better = best
                .as_ref()
                .map_or(true, |(_, _, best_score)| score < *best_score);
            if better {
                best = Some((employee.id.clone(), finish, score));
            }
        }

        processed.insert(task.id.clone());
        match best {
            Some((eid, finish, _)) => {
                let employee = req
                    .employees
                    .iter()
                    .find(|e| e.id == eid)
                    .expect("empleado asignado");
                let duration = domain::duration_for(req, task, employee).expect("elegible");
                assignment.insert(task.id.clone(), eid.clone());
                completion.insert(task.id.clone(), finish);
                clock.insert(eid.clone(), finish);
                *workload.entry(eid.clone()).or_insert(0) += duration;
            }
            None => {
                unassigned.push(task.id.clone());
                warnings.push(format!(
                    "UNASSIGNABLE: la tarea {} no tiene ningún empleado elegible",
                    task.id
                ));
            }
        }
    }

    // Tareas que nunca estuvieron listas porque una dependencia no se asignó.
    for task in plannable.iter().filter(|t| !processed.contains(&t.id)) {
        unassigned.push(task.id.clone());
        warnings.push(format!(
            "BLOCKED_BY_DEPENDENCY: la tarea {} depende de una tarea no asignada",
            task.id
        ));
    }

    unassigned.sort();
    unassigned.dedup();
    warnings.sort();
    warnings.dedup();

    let makespan = completion.values().copied().max().unwrap_or(0);

    (assignment, unassigned, warnings, workload, makespan)
}

/// Empleados elegibles (proxy de escasez de habilidades).
fn scarcity(task: &Task, req: &PlanRequest) -> usize {
    domain::eligible_employees(req, task).len()
}

fn has_dependencies(req: &PlanRequest) -> bool {
    req.tasks
        .iter()
        .any(|t| t.is_plannable() && !t.dependencies.is_empty())
}

fn makespan(workload: &BTreeMap<String, u32>) -> u32 {
    workload.values().copied().max().unwrap_or(0)
}

/// Búsqueda local acotada: un movimiento o intercambio por iteración, el que más
/// reduzca el makespan, siempre que supere el umbral de mejora.
fn local_search(
    req: &PlanRequest,
    mut assignment: BTreeMap<String, String>,
    mut workload: BTreeMap<String, u32>,
) -> (BTreeMap<String, String>, BTreeMap<String, u32>) {
    let threshold = req.options.improvement_threshold_minutes;
    let max_changes = req.options.max_changes_per_cycle;
    let mut applied = 0u32;

    for _ in 0..100 {
        if applied >= max_changes {
            break;
        }

        let baseline = makespan(&workload);
        let mut best: Option<(u32, BTreeMap<String, String>, BTreeMap<String, u32>)> = None;

        // Movimientos individuales.
        for (task_id, from) in &assignment {
            let task = req.tasks.iter().find(|t| &t.id == task_id).unwrap();
            let from_emp = req.employees.iter().find(|e| e.id == *from).unwrap();
            let d_from = domain::duration_for(req, task, from_emp).unwrap();
            for employee in domain::eligible_employees(req, task) {
                if employee.id == *from {
                    continue;
                }
                let d_to = domain::duration_for(req, task, employee).unwrap();

                let mut new_workload = workload.clone();
                *new_workload.get_mut(from).unwrap() -= d_from;
                *new_workload.entry(employee.id.clone()).or_insert(0) += d_to;
                let new_makespan = makespan(&new_workload);

                if baseline >= new_makespan + threshold {
                    let improvement = baseline - new_makespan;
                    if best
                        .as_ref()
                        .map_or(true, |(best_imp, _, _)| improvement > *best_imp)
                    {
                        let mut new_assignment = assignment.clone();
                        new_assignment.insert(task_id.clone(), employee.id.clone());
                        best = Some((improvement, new_assignment, new_workload));
                    }
                }
            }
        }

        // Intercambios entre dos tareas de empleados distintos.
        let task_ids: Vec<String> = assignment.keys().cloned().collect();
        for i in 0..task_ids.len() {
            for j in (i + 1)..task_ids.len() {
                let (ta, tb) = (&task_ids[i], &task_ids[j]);
                let ea = assignment[ta].clone();
                let eb = assignment[tb].clone();
                if ea == eb {
                    continue;
                }
                let (task_a, task_b) = (
                    req.tasks.iter().find(|t| &t.id == ta).unwrap(),
                    req.tasks.iter().find(|t| &t.id == tb).unwrap(),
                );
                let (emp_a, emp_b) = (
                    req.employees.iter().find(|e| e.id == ea).unwrap(),
                    req.employees.iter().find(|e| e.id == eb).unwrap(),
                );
                // Ambos deben ser elegibles para el empleado del otro.
                let (Some(d_a_on_eb), Some(d_b_on_ea)) = (
                    domain::duration_for(req, task_a, emp_b),
                    domain::duration_for(req, task_b, emp_a),
                ) else {
                    continue;
                };
                let d_a_on_ea = domain::duration_for(req, task_a, emp_a).unwrap();
                let d_b_on_eb = domain::duration_for(req, task_b, emp_b).unwrap();

                let mut new_workload = workload.clone();
                let ea_new = new_workload[&ea] - d_a_on_ea + d_b_on_ea;
                let eb_new = new_workload[&eb] - d_b_on_eb + d_a_on_eb;
                new_workload.insert(ea.clone(), ea_new);
                new_workload.insert(eb.clone(), eb_new);
                let new_makespan = makespan(&new_workload);

                if baseline >= new_makespan + threshold {
                    let improvement = baseline - new_makespan;
                    if best
                        .as_ref()
                        .map_or(true, |(best_imp, _, _)| improvement > *best_imp)
                    {
                        let mut new_assignment = assignment.clone();
                        new_assignment.insert(ta.clone(), eb.clone());
                        new_assignment.insert(tb.clone(), ea.clone());
                        best = Some((improvement, new_assignment, new_workload));
                    }
                }
            }
        }

        match best {
            Some((_, new_assignment, new_workload)) => {
                assignment = new_assignment;
                workload = new_workload;
                applied += 1;
            }
            None => break,
        }
    }

    (assignment, workload)
}

/// Cambios frente a la asignación actual (solo tareas que ya tenían empleado).
fn diff_changes(req: &PlanRequest, assignment: &BTreeMap<String, String>) -> Vec<Change> {
    let mut changes = Vec::new();
    for task in req.tasks.iter().filter(|t| t.is_plannable()) {
        if let Some(current) = &task.current_employee_id {
            if let Some(next) = assignment.get(&task.id) {
                if next != current {
                    changes.push(Change {
                        task_id: task.id.clone(),
                        from_employee_id: Some(current.clone()),
                        to_employee_id: next.clone(),
                        reason: "lower_projected_makespan".to_string(),
                    });
                }
            }
        }
    }
    changes.sort_by(|a, b| a.task_id.cmp(&b.task_id));
    changes
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Employee, Options, TaskStatus};

    fn example() -> PlanRequest {
        PlanRequest {
            horizon_minutes: 480,
            employees: vec![
                Employee {
                    id: "E1".into(),
                    available_minutes: 420,
                    skills: vec!["packing".into(), "labeling".into()],
                    shifts: vec![],
                },
                Employee {
                    id: "E2".into(),
                    available_minutes: 420,
                    skills: vec!["packing".into()],
                    shifts: vec![],
                },
            ],
            tasks: vec![
                Task {
                    id: "T1".into(),
                    status: TaskStatus::Pending,
                    task_type: "packing".into(),
                    current_employee_id: Some("E2".into()),
                    employee_id: None,
                    remaining_minutes: None,
                    estimated_minutes_by_employee: [("E1".into(), 15), ("E2".into(), 25)]
                        .into_iter()
                        .collect(),
                    priority: 0,
                    deadline_minutes: None,
                    dependencies: vec![],
                },
                Task {
                    id: "T2".into(),
                    status: TaskStatus::Pending,
                    task_type: "labeling".into(),
                    current_employee_id: None,
                    employee_id: None,
                    remaining_minutes: None,
                    estimated_minutes_by_employee: [("E1".into(), 20)].into_iter().collect(),
                    priority: 0,
                    deadline_minutes: None,
                    dependencies: vec![],
                },
                Task {
                    id: "T3".into(),
                    status: TaskStatus::Running,
                    task_type: "packing".into(),
                    current_employee_id: None,
                    employee_id: Some("E1".into()),
                    remaining_minutes: Some(10),
                    estimated_minutes_by_employee: Default::default(),
                    priority: 0,
                    deadline_minutes: None,
                    dependencies: vec![],
                },
            ],
            options: Options::default(),
            ..Default::default()
        }
    }

    fn task(id: &str, task_type: &str, estimates: &[(&str, u32)], deps: &[&str]) -> Task {
        Task {
            id: id.into(),
            status: TaskStatus::Pending,
            task_type: task_type.into(),
            current_employee_id: None,
            employee_id: None,
            remaining_minutes: None,
            estimated_minutes_by_employee: estimates
                .iter()
                .map(|(e, d)| (e.to_string(), *d))
                .collect(),
            priority: 0,
            deadline_minutes: None,
            dependencies: deps.iter().map(|d| d.to_string()).collect(),
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

    #[tokio::test]
    async fn plan_de_ejemplo_es_factible() {
        let solution = HeuristicSolver::default().solve(&example()).await.unwrap();
        assert_eq!(solution.running_tasks_unchanged, vec!["T3"]);
        assert_eq!(solution.makespan_minutes, Some(30));
        assert!(solution
            .assignments
            .iter()
            .any(|a| a.task_id == "T2" && a.employee_id == "E1"));
        assert!(solution
            .assignments
            .iter()
            .any(|a| a.task_id == "T1" && a.employee_id == "E2"));
        assert!(solution.unassigned_tasks.is_empty());
    }

    #[tokio::test]
    async fn el_movimiento_mejora_el_makespan() {
        let req = PlanRequest {
            horizon_minutes: 100,
            employees: vec![employee("A", &["x"]), employee("B", &["x"])],
            tasks: vec![
                task("U", "x", &[("A", 10), ("B", 100)], &[]),
                task("V", "x", &[("A", 100), ("B", 10)], &[]),
            ],
            options: Options::default(),
            ..Default::default()
        };
        let solution = HeuristicSolver::default().solve(&req).await.unwrap();
        assert_eq!(solution.makespan_minutes, Some(10));
    }

    #[tokio::test]
    async fn las_dependencias_retrasan_la_planificacion() {
        // B depende de A: aunque B puede ir a E2 en 10 min, debe esperar a que A
        // (E1, 10 min) termine → makespan 20 en lugar de 10.
        let req = PlanRequest {
            horizon_minutes: 100,
            employees: vec![employee("E1", &["x"]), employee("E2", &["x"])],
            tasks: vec![
                task("A", "x", &[("E1", 10), ("E2", 100)], &[]),
                task("B", "x", &[("E1", 100), ("E2", 10)], &["A"]),
            ],
            options: Options::default(),
            ..Default::default()
        };
        let solution = HeuristicSolver::default().solve(&req).await.unwrap();
        assert_eq!(solution.makespan_minutes, Some(20));
        assert!(solution
            .assignments
            .iter()
            .any(|a| a.task_id == "A" && a.employee_id == "E1"));
        assert!(solution
            .assignments
            .iter()
            .any(|a| a.task_id == "B" && a.employee_id == "E2"));
    }

    #[tokio::test]
    async fn una_dependencia_inasignable_bloquea_a_sus_dependientes() {
        // A no tiene empleado elegible → B (depende de A) queda bloqueada.
        let req = PlanRequest {
            horizon_minutes: 100,
            employees: vec![employee("E1", &["x"])],
            tasks: vec![
                task("A", "y", &[], &[]), // nadie tiene skill "y"
                task("B", "x", &[("E1", 10)], &["A"]),
            ],
            options: Options::default(),
            ..Default::default()
        };
        let solution = HeuristicSolver::default().solve(&req).await.unwrap();
        assert!(solution.unassigned_tasks.contains(&"A".to_string()));
        assert!(solution.unassigned_tasks.contains(&"B".to_string()));
        assert!(solution
            .warnings
            .iter()
            .any(|w| w.contains("BLOCKED_BY_DEPENDENCY")));
    }

    #[tokio::test]
    async fn el_fallback_de_cold_start_asigna_al_equipo() {
        // C no tiene estimación explícita, pero la media del equipo (15) le
        // permite ser elegible.
        let req = PlanRequest {
            horizon_minutes: 100,
            employees: vec![
                employee("A", &["x"]),
                employee("B", &["x"]),
                employee("C", &["x"]),
            ],
            tasks: vec![task("T", "x", &[("A", 10), ("B", 20)], &[])],
            options: Options::default(),
            ..Default::default()
        };
        let solution = HeuristicSolver::default().solve(&req).await.unwrap();
        assert_eq!(solution.makespan_minutes, Some(10));
        assert!(solution
            .assignments
            .iter()
            .any(|a| a.task_id == "T" && a.employee_id == "A"));
    }
}
