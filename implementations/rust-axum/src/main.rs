use std::env;
use std::sync::OnceLock;
use std::time::{Duration, Instant};

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use chrono::{DateTime, Utc};
use futures::future::join_all;
use serde::Serialize;
use serde_json::json;
use sha2::{Digest, Sha256};
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};

#[derive(Serialize)]
struct StaticUser {
    id: i64,
    name: &'static str,
    email: &'static str,
}

#[derive(Serialize)]
struct User {
    id: i32,
    name: String,
    email: String,
    created_at: DateTime<Utc>,
}

fn env_or(key: &str, default: &str) -> String {
    env::var(key).unwrap_or_else(|_| default.to_string())
}

/// One process-wide reqwest client. A per-request `Client::new()` discards the
/// connection pool each call, churning connections under a concurrent fan-out
/// and dropping requests; a shared client keeps connections alive and reused.
static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(|| {
        reqwest::Client::builder()
            .pool_max_idle_per_host(200)
            .timeout(Duration::from_secs(10))
            .build()
            .expect("failed to build reqwest client")
    })
}

fn build_database_url() -> String {
    let host = env_or("DB_HOST", "postgres");
    let port = env_or("DB_PORT", "5432");
    let name = env_or("DB_NAME", "benchmark");
    let user = env_or("DB_USER", "benchmark");
    let password = env_or("DB_PASSWORD", "benchmark");
    format!(
        "postgres://{}:{}@{}:{}/{}",
        user, password, host, port, name
    )
}

/// Create a pool, retrying for ~30s so a brief DB startup delay does not crash the app.
async fn connect_with_retry(database_url: &str) -> PgPool {
    let max_attempts = 30u32;
    for attempt in 1..=max_attempts {
        let pool_result = PgPoolOptions::new()
            .max_connections(10)
            .acquire_timeout(Duration::from_secs(5))
            .connect(database_url)
            .await;

        match pool_result {
            Ok(pool) => {
                eprintln!("Connected to database (attempt {})", attempt);
                return pool;
            }
            Err(e) => {
                eprintln!(
                    "DB connection attempt {}/{} failed: {}",
                    attempt, max_attempts, e
                );
                tokio::time::sleep(Duration::from_secs(1)).await;
            }
        }
    }
    panic!("Could not connect to the database after {} attempts", max_attempts);
}

async fn health() -> impl IntoResponse {
    Json(json!({ "status": "ok" }))
}

async fn serialize() -> impl IntoResponse {
    Json(StaticUser {
        id: 123,
        name: "John Doe",
        email: "john@example.com",
    })
}

async fn get_user(
    State(pool): State<PgPool>,
    Path(id): Path<i32>,
) -> impl IntoResponse {
    let result = sqlx::query(
        "SELECT id, name, email, created_at FROM users WHERE id = $1",
    )
    .bind(id)
    .fetch_one(&pool)
    .await;

    match result {
        Ok(row) => {
            let user = User {
                id: row.get("id"),
                name: row.get("name"),
                email: row.get("email"),
                created_at: row.get("created_at"),
            };
            (StatusCode::OK, Json(json!(user))).into_response()
        }
        Err(sqlx::Error::RowNotFound) => {
            (StatusCode::NOT_FOUND, Json(json!({ "error": "not found" }))).into_response()
        }
        Err(e) => {
            eprintln!("Database error fetching user {}: {}", id, e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": "internal server error" })),
            )
                .into_response()
        }
    }
}

async fn cpu(Path(rounds): Path<i64>) -> impl IntoResponse {
    if rounds <= 0 {
        return (StatusCode::NOT_FOUND, Json(json!({ "error": "not found" }))).into_response();
    }

    let rounds = rounds.min(10_000_000);

    // CPU-bound work: run on a blocking thread so we do not stall the async runtime.
    let hash = tokio::task::spawn_blocking(move || {
        let seed = b"backend-decision-lab";
        let mut digest = Sha256::digest(seed);
        for _ in 1..rounds {
            digest = Sha256::digest(&digest);
        }
        hex::encode(digest)
    })
    .await
    .expect("hashing task panicked");

    (StatusCode::OK, Json(json!({ "rounds": rounds, "hash": hash }))).into_response()
}

async fn aggregate() -> impl IntoResponse {
    let upstream_url = env_or("UPSTREAM_URL", "http://upstream:8080");
    let url = format!("{}/delay/0.05", upstream_url);

    let client = http_client();

    let start = Instant::now();

    let requests = (0..10).map(|_| {
        let url = url.clone();
        async move {
            match client.get(&url).send().await {
                Ok(resp) => resp.status() == reqwest::StatusCode::OK,
                Err(_) => false,
            }
        }
    });

    let results = join_all(requests).await;

    let took_ms = start.elapsed().as_millis();
    let succeeded = results.iter().filter(|&&ok| ok).count();

    (
        StatusCode::OK,
        Json(json!({ "requests": 10, "succeeded": succeeded, "took_ms": took_ms })),
    )
        .into_response()
}

#[tokio::main]
async fn main() {
    let database_url = build_database_url();
    let pool = connect_with_retry(&database_url).await;

    let app = Router::new()
        .route("/health", get(health))
        .route("/serialize", get(serialize))
        .route("/users/:id", get(get_user))
        .route("/cpu/:rounds", get(cpu))
        .route("/aggregate", get(aggregate))
        .with_state(pool);

    let app_port = env_or("APP_PORT", "8000");
    let addr = format!("0.0.0.0:{}", app_port);

    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .unwrap_or_else(|e| panic!("Failed to bind to {}: {}", addr, e));

    eprintln!("Listening on {}", addr);

    axum::serve(listener, app)
        .await
        .expect("Server error");
}
