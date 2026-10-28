use std::collections::BTreeSet;

use crate::model::{PlanRequest, UpdatedEstimate};

/// Actualización por media móvil exponencial (EMA) de una estimación previa con
/// una observación real reciente.
///
/// `alpha` controla cuánto pesa la observación reciente (0..1). Un valor alto
/// adapta rápido pero es más sensible a valores atípicos.
pub fn apply_ema(prior: u32, actual: u32, alpha: f64) -> u32 {
    let a = alpha.clamp(0.0, 1.0);
    (a * actual as f64 + (1.0 - a) * prior as f64).round() as u32
}

/// Estimaciones de duración actualizadas (EMA) para cada observación de
/// (empleado, tipo de actividad) recibida. La estimación previa se obtiene de
/// la media de las estimaciones por tarea presentes en la propia solicitud.
pub fn updated_estimates(req: &PlanRequest) -> Vec<UpdatedEstimate> {
    let alpha = req.options.ema_alpha;
    let mut seen: BTreeSet<(String, String)> = BTreeSet::new();
    let mut out = Vec::new();

    for obs in &req.duration_observations {
        let key = (obs.employee_id.clone(), obs.task_type.clone());
        if !seen.insert(key) {
            continue;
        }
        let prior =
            prior_estimate(req, &obs.employee_id, &obs.task_type).unwrap_or(obs.actual_minutes);
        let duration_minutes = apply_ema(prior, obs.actual_minutes, alpha);
        out.push(UpdatedEstimate {
            employee_id: obs.employee_id.clone(),
            task_type: obs.task_type.clone(),
            duration_minutes,
        });
    }

    out.sort_by(|a, b| {
        a.employee_id
            .cmp(&b.employee_id)
            .then_with(|| a.task_type.cmp(&b.task_type))
    });
    out
}

/// Estimación previa por (empleado, tipo): media de las estimaciones por tarea
/// planificable de ese tipo para ese empleado.
fn prior_estimate(req: &PlanRequest, employee_id: &str, task_type: &str) -> Option<u32> {
    let values: Vec<u32> = req
        .tasks
        .iter()
        .filter(|t| t.is_plannable() && t.task_type == task_type)
        .filter_map(|t| t.estimated_minutes_by_employee.get(employee_id).copied())
        .collect();
    if values.is_empty() {
        return None;
    }
    let sum: u64 = values.iter().map(|&v| v as u64).sum();
    Some((sum / values.len() as u64) as u32)
}

/// Proyección de demanda futura: repite la media del historial de llegadas
/// durante los próximos `periods` períodos. Devuelve un vector vacío si no hay
/// historial o si `periods` es 0.
pub fn forecast_demand(history: &[u32], periods: u32) -> Vec<u32> {
    if periods == 0 || history.is_empty() {
        return Vec::new();
    }
    let avg = history.iter().map(|&v| v as u64).sum::<u64>() / history.len() as u64;
    vec![avg as u32; periods as usize]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{DurationObservation, Options, PlanRequest, Task, TaskStatus};

    #[test]
    fn el_ema_pondera_la_observacion_reciente() {
        // alpha 0.5: 0.5*40 + 0.5*20 = 30.
        assert_eq!(apply_ema(20, 40, 0.5), 30);
        // alpha 1.0: solo la observación.
        assert_eq!(apply_ema(20, 40, 1.0), 40);
        // alpha 0.0: solo la estimación previa.
        assert_eq!(apply_ema(20, 40, 0.0), 20);
    }

    fn plan() -> PlanRequest {
        PlanRequest {
            horizon_minutes: 480,
            employees: vec![],
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
            options: Options {
                ema_alpha: 0.5,
                ..Default::default()
            },
            duration_observations: vec![DurationObservation {
                employee_id: "E1".into(),
                task_type: "packing".into(),
                actual_minutes: 30,
            }],
            arrival_history: vec![5, 6, 7],
        }
    }

    #[test]
    fn actualiza_las_estimaciones_por_ema() {
        let updated = updated_estimates(&plan());
        assert_eq!(updated.len(), 1);
        assert_eq!(updated[0].employee_id, "E1");
        assert_eq!(updated[0].task_type, "packing");
        // prior 20, actual 30, alpha 0.5 → 25.
        assert_eq!(updated[0].duration_minutes, 25);
    }

    #[test]
    fn proyecta_la_demanda_media() {
        // media de [5,6,7] = 6, repetida 3 períodos.
        assert_eq!(forecast_demand(&[5, 6, 7], 3), vec![6, 6, 6]);
        assert_eq!(forecast_demand(&[5, 6, 7], 0), Vec::<u32>::new());
        assert_eq!(forecast_demand(&[], 3), Vec::<u32>::new());
    }
}
