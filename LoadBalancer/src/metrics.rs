use std::sync::atomic::{AtomicU64, Ordering};

/// Contador global de solicitudes `POST /v1/plan` (observabilidad mínima; el
/// servicio es stateless, así que no se persiste estado operativo).
static PLAN_REQUESTS_TOTAL: AtomicU64 = AtomicU64::new(0);

pub fn record_plan_request() {
    PLAN_REQUESTS_TOTAL.fetch_add(1, Ordering::Relaxed);
}

/// Render en formato de texto Prometheus.
pub fn render() -> String {
    let total = PLAN_REQUESTS_TOTAL.load(Ordering::Relaxed);
    format!(
        "# HELP load_balancer_plan_requests_total Total de solicitudes POST /v1/plan.\n\
         # TYPE load_balancer_plan_requests_total counter\n\
         load_balancer_plan_requests_total {total}\n"
    )
}
