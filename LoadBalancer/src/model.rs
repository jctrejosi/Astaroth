use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanRequest {
    pub horizon_minutes: u32,
    pub employees: Vec<Employee>,
    pub tasks: Vec<Task>,
    #[serde(default)]
    pub options: Options,
    /// Observaciones recientes de duración real, para actualizar las
    /// estimaciones por EMA (aprendizaje operativo).
    #[serde(default)]
    pub duration_observations: Vec<DurationObservation>,
    /// Historial de llegadas de actividades (conteos por período), para
    /// proyectar demanda futura.
    #[serde(default)]
    pub arrival_history: Vec<u32>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Employee {
    pub id: String,
    #[serde(default)]
    pub available_minutes: u32,
    #[serde(default)]
    pub skills: Vec<String>,
    #[serde(default)]
    pub shifts: Vec<Shift>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Shift {
    pub start_minutes: u32,
    pub end_minutes: u32,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Task {
    pub id: String,
    pub status: TaskStatus,
    #[serde(rename = "type")]
    pub task_type: String,
    #[serde(default)]
    pub current_employee_id: Option<String>,
    #[serde(default)]
    pub employee_id: Option<String>,
    #[serde(default)]
    pub remaining_minutes: Option<u32>,
    #[serde(default)]
    pub estimated_minutes_by_employee: BTreeMap<String, u32>,
    #[serde(default)]
    pub priority: u32,
    #[serde(default)]
    pub deadline_minutes: Option<u32>,
    #[serde(default)]
    pub dependencies: Vec<String>,
}

/// Observación de duración real para una combinación empleado/tipo de actividad.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DurationObservation {
    pub employee_id: String,
    #[serde(rename = "type")]
    pub task_type: String,
    pub actual_minutes: u32,
}

impl Task {
    pub fn is_running(&self) -> bool {
        self.status == TaskStatus::Running
    }

    pub fn is_plannable(&self) -> bool {
        matches!(self.status, TaskStatus::Pending | TaskStatus::Assigned)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TaskStatus {
    Pending,
    Assigned,
    Running,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SolverChoice {
    Heuristic,
    Highs,
}

impl Default for SolverChoice {
    fn default() -> Self {
        SolverChoice::Heuristic
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Options {
    #[serde(default)]
    pub solver: SolverChoice,
    #[serde(default)]
    pub time_limit_seconds: Option<f64>,
    #[serde(default = "default_true")]
    pub enforce_capacity: bool,
    /// Mejora mínima (en minutos) para aceptar un movimiento o intercambio.
    #[serde(default = "default_one")]
    pub improvement_threshold_minutes: u32,
    /// Límite de cambios aplicados por ciclo de rebalanceo.
    #[serde(default = "default_hundred")]
    pub max_changes_per_cycle: u32,
    /// Peso de las observaciones recientes en el estimador EMA.
    #[serde(default = "default_ema_alpha")]
    pub ema_alpha: f64,
    /// Períodos a proyectar en el forecast de demanda (0 = desactivado).
    #[serde(default)]
    pub forecast_periods: u32,
}

fn default_true() -> bool {
    true
}

fn default_one() -> u32 {
    1
}

fn default_hundred() -> u32 {
    100
}

fn default_ema_alpha() -> f64 {
    0.3
}

impl Default for Options {
    fn default() -> Self {
        Self {
            solver: SolverChoice::Heuristic,
            time_limit_seconds: None,
            enforce_capacity: true,
            improvement_threshold_minutes: 1,
            max_changes_per_cycle: 100,
            ema_alpha: 0.3,
            forecast_periods: 0,
        }
    }
}

// ── Respuesta ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
pub struct PlanResponse {
    pub status: PlanStatus,
    pub makespan_minutes: Option<u32>,
    pub assignments: Vec<Assignment>,
    pub running_tasks_unchanged: Vec<String>,
    pub changes: Vec<Change>,
    pub capacity: CapacityReport,
    pub unassigned_tasks: Vec<String>,
    pub solver: SolverInfo,
    pub warnings: Vec<String>,
    /// Estimaciones de duración actualizadas (EMA) por empleado/tipo.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub updated_estimates: Vec<UpdatedEstimate>,
    /// Proyección de demanda para los próximos períodos.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub demand_forecast: Vec<u32>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PlanStatus {
    Feasible,
    CapacityShortage,
    Unassignable,
    Unknown,
}

#[derive(Debug, Clone, Serialize)]
pub struct Assignment {
    pub task_id: String,
    pub employee_id: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct Change {
    pub task_id: String,
    pub from_employee_id: Option<String>,
    pub to_employee_id: String,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct CapacityReport {
    pub required_minutes: u32,
    pub available_minutes: u32,
    pub shortage_minutes: u32,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct SolverInfo {
    pub method: String,
    pub optimality_proven: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct UpdatedEstimate {
    pub employee_id: String,
    pub task_type: String,
    pub duration_minutes: u32,
}
