mod capacity;
mod config;
mod domain;
mod error;
mod estimator;
mod highs;
mod metrics;
mod milp;
mod model;
mod orchestrator;
mod solver;
mod validator;

use axum::{extract::State, routing::get, routing::post, Json, Router};
use tracing::info;

use crate::config::Config;
use crate::error::ApiError;
use crate::model::{PlanRequest, PlanResponse, SolverChoice};
use crate::solver::{HeuristicSolver, Solver};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "load_balancer=info".into()),
        )
        .init();

    let config = Config::from_env();
    info!(highs_url = %config.highs_url, port = config.port, "arrancando balanceador");

    let bind_addr = format!("0.0.0.0:{}", config.port);
    let listener = tokio::net::TcpListener::bind(&bind_addr)
        .await
        .unwrap_or_else(|e| panic!("no se pudo enlazar {bind_addr}: {e}"));
    info!("escuchando en http://{bind_addr}");

    let app = Router::new()
        .route("/v1/plan", post(plan))
        .route("/health", get(health))
        .route("/metrics", get(metrics))
        .with_state(config);

    axum::serve(listener, app).await.expect("servidor detenido");
}

async fn health() -> &'static str {
    "ok"
}

async fn metrics() -> String {
    crate::metrics::render()
}

/// `POST /v1/plan`: planifica a partir de una instantánea sin estado.
async fn plan(
    State(config): State<Config>,
    Json(req): Json<PlanRequest>,
) -> Result<Json<PlanResponse>, ApiError> {
    info!(
        horizon_minutes = req.horizon_minutes,
        tasks = req.tasks.len(),
        employees = req.employees.len(),
        solver = ?req.options.solver,
        "solicitud de planificación"
    );
    crate::metrics::record_plan_request();

    validator::validate(&req)?;

    let solution = match req.options.solver {
        SolverChoice::Heuristic => HeuristicSolver::default().solve(&req).await?,
        SolverChoice::Highs => highs::HighsHttpSolver::new(config).solve(&req).await?,
    };

    Ok(Json(orchestrator::build_response(&req, solution)))
}
