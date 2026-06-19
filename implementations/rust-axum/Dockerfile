# ---- Build stage ----
FROM rust:1-bookworm AS builder

WORKDIR /app

# Cache dependencies: copy manifests first and build a dummy main so the
# dependency layer is reused when only source changes.
COPY Cargo.toml ./
RUN mkdir src && echo "fn main() {}" > src/main.rs \
    && cargo build --release \
    && rm -rf src

# Now copy the real source and build the actual binary.
COPY src ./src
# Touch main.rs so cargo recompiles it (timestamp newer than the dummy build).
RUN touch src/main.rs && cargo build --release

# ---- Runtime stage ----
FROM debian:bookworm-slim AS runtime

# sqlx with rustls is pure-Rust (no libpq needed); ca-certificates is enough
# for TLS trust roots. Postgres connection here is plaintext, but include them
# to be safe and standard.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/target/release/rust-axum-benchmark /usr/local/bin/rust-axum-benchmark

ENV APP_PORT=8000
EXPOSE 8000

CMD ["rust-axum-benchmark"]
