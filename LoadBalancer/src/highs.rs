use serde::{Deserialize, Serialize};

use crate::config::Config;
use crate::error::ApiError;
use crate::model::{Assignment, Change, PlanRequest, PlanStatus, SolverInfo, TaskStatus};
use crate::solver::{Solution, Solver};

// ── Contrato de entrada de HiGHS ─────────────────────────────────

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize)]
pub struct HighsMipRequest {
    pub objective: HighsObjective,
    pub constraints: Vec<HighsConstraint>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bounds: Option<Vec<HighsBound>>,
    pub integrality: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<HighsMipOptions>,
}

#[derive(Debug, Clone, Serialize)]
pub struct HighsObjective {
    pub sense: String,
    pub coefficients: Vec<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct HighsConstraint {
    pub coefficients: Vec<f64>,
    pub sense: String,
    pub rhs: f64,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize)]
pub struct HighsBound {
    pub lower: Option<f64>,
    pub upper: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct HighsMipOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub time_limit: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mip_rel_gap: Option<f64>,
}

// ── Contrato de salida de HiGHS ──────────────────────────────────

#[derive(Debug, Clone, Deserialize)]
pub struct HighsSolveResponse {
    pub status: String,
    pub objective_value: Option<f64>,
    pub variables: Option<Vec<f64>>,
    #[serde(default)]
    #[allow(dead_code)]
    pub metadata: HighsMetadata,
    #[allow(dead_code)]
    pub message: Option<String>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Default, Deserialize)]
pub struct HighsMetadata {
    pub solver_used: String,
    pub engine_version: String,
    pub solve_time_ms: Option<f64>,
    pub gap: Option<f64>,
}

// ── Solver vía HTTP ──────────────────────────────────────────────

/// Implementación de `Solver` que delega en el servicio `Astaroth/highs`.
pub struct HighsHttpSolver {
    config: Config,
}

impl HighsHttpSolver {
    pub fn new(config: Config) -> Self {
        Self { config }
    }
}

impl Solver for HighsHttpSolver {
    fn method(&self) -> &'static str {
        "highs_mip"
    }

    async fn solve(&self, req: &PlanRequest) -> Result<Solution, ApiError> {
        let mip = crate::milp::build_assignment_mip(req, req.options.time_limit_seconds);
        let url = format!(
            "{}/v1/mip/solve",
            self.config.highs_url.trim_end_matches('/')
        );

        let client = reqwest::Client::new();
        let mut builder = client.post(&url).json(&mip.request);
        if let Some(key) = &self.config.highs_api_key {
            builder = builder.header("X-API-Key", key.as_str());
        }

        let response = builder
            .send()
            .await
            .map_err(|e| ApiError::SolverUnavailable(e.to_string()))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(ApiError::SolverUnavailable(format!(
                "highs {status}: {body}"
            )));
        }

        let parsed: HighsSolveResponse = response
            .json()
            .await
            .map_err(|e| ApiError::Internal(e.to_string()))?;

        Ok(self.map_response(req, &mip.var_map, parsed))
    }
}

impl HighsHttpSolver {
    fn map_response(
        &self,
        req: &PlanRequest,
        var_map: &[Option<(String, String)>],
        r: HighsSolveResponse,
    ) -> Solution {
        let running: Vec<String> = req
            .tasks
            .iter()
            .filter(|t| t.status == TaskStatus::Running)
            .map(|t| t.id.clone())
            .collect();

        let mut assignments = Vec::new();
        if let Some(vars) = &r.variables {
            for (idx, value) in vars.iter().enumerate() {
                if let Some(Some((employee_id, task_id))) = var_map.get(idx) {
                    if *value > 0.5 {
                        assignments.push(Assignment {
                            task_id: (*task_id).clone(),
                            employee_id: (*employee_id).clone(),
                        });
                    }
                }
            }
        }

        let mut changes = Vec::new();
        let mut unassigned = Vec::new();
        for task in req.tasks.iter().filter(|t| t.is_plannable()) {
            let assigned = assignments
                .iter()
                .find(|a| a.task_id == task.id)
                .map(|a| a.employee_id.clone());
            match assigned {
                Some(employee_id) => {
                    if let Some(current) = &task.current_employee_id {
                        if current != &employee_id {
                            changes.push(Change {
                                task_id: task.id.clone(),
                                from_employee_id: Some(current.clone()),
                                to_employee_id: employee_id,
                                reason: "milp_optimal".to_string(),
                            });
                        }
                    }
                }
                None => unassigned.push(task.id.clone()),
            }
        }
        unassigned.sort();
        changes.sort_by(|a, b| a.task_id.cmp(&b.task_id));

        let optimal = r.status == "optimal";
        let mut warnings = Vec::new();
        if !optimal {
            warnings.push(format!("SOLVER_STATUS: {}", r.status));
        }

        let status_hint = match r.status.as_str() {
            "optimal" => Some(PlanStatus::Feasible),
            "infeasible" => Some(PlanStatus::CapacityShortage),
            "time_limit" | "iteration_limit" | "unknown" => Some(PlanStatus::Unknown),
            _ => Some(PlanStatus::Unknown),
        };

        Solution {
            makespan_minutes: r.objective_value.map(|v| v.round() as u32),
            assignments,
            changes,
            running_tasks_unchanged: running,
            unassigned_tasks: unassigned,
            solver: SolverInfo {
                method: self.method().to_string(),
                optimality_proven: optimal,
            },
            warnings,
            status_hint,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::Config;
    use crate::model::{Employee, Options, PlanRequest, Task, TaskStatus};

    fn config() -> Config {
        Config {
            port: 8016,
            highs_url: "http://127.0.0.1:8015".into(),
            highs_api_key: None,
        }
    }

    fn req() -> PlanRequest {
        PlanRequest {
            horizon_minutes: 100,
            employees: vec![
                Employee {
                    id: "E1".into(),
                    available_minutes: 100,
                    skills: vec!["x".into()],
                    shifts: vec![],
                },
                Employee {
                    id: "E2".into(),
                    available_minutes: 100,
                    skills: vec!["x".into()],
                    shifts: vec![],
                },
            ],
            tasks: vec![
                Task {
                    id: "T1".into(),
                    status: TaskStatus::Pending,
                    task_type: "x".into(),
                    current_employee_id: None,
                    employee_id: None,
                    remaining_minutes: None,
                    estimated_minutes_by_employee: [("E1".into(), 10)].into_iter().collect(),
                    priority: 0,
                    deadline_minutes: None,
                    dependencies: vec![],
                },
                Task {
                    id: "T2".into(),
                    status: TaskStatus::Pending,
                    task_type: "x".into(),
                    current_employee_id: None,
                    employee_id: None,
                    remaining_minutes: None,
                    estimated_minutes_by_employee: [("E2".into(), 20)].into_iter().collect(),
                    priority: 0,
                    deadline_minutes: None,
                    dependencies: vec![],
                },
            ],
            options: Options::default(),
            ..Default::default()
        }
    }

    #[test]
    fn mapea_respuesta_optimal_a_solution() {
        let solver = HighsHttpSolver::new(config());
        let var_map = vec![
            Some(("E1".to_string(), "T1".to_string())),
            Some(("E2".to_string(), "T2".to_string())),
            None,
        ];
        let r = HighsSolveResponse {
            status: "optimal".into(),
            objective_value: Some(30.0),
            variables: Some(vec![1.0, 1.0, 30.0]),
            metadata: Default::default(),
            message: None,
        };
        let sol = solver.map_response(&req(), &var_map, r);
        assert_eq!(sol.makespan_minutes, Some(30));
        assert_eq!(sol.assignments.len(), 2);
        assert!(sol.solver.optimality_proven);
        assert_eq!(sol.status_hint, Some(PlanStatus::Feasible));
        assert!(sol.unassigned_tasks.is_empty());
    }

    #[test]
    fn mapea_infeasible_a_capacity_shortage() {
        let solver = HighsHttpSolver::new(config());
        let var_map = vec![None];
        let r = HighsSolveResponse {
            status: "infeasible".into(),
            objective_value: None,
            variables: None,
            metadata: Default::default(),
            message: Some("infeasible".into()),
        };
        let sol = solver.map_response(&req(), &var_map, r);
        assert_eq!(sol.status_hint, Some(PlanStatus::CapacityShortage));
        assert!(!sol.solver.optimality_proven);
    }
}
