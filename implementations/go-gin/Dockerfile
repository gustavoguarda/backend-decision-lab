# syntax=docker/dockerfile:1

# ---- build stage ----
FROM golang:1.22-alpine AS build

WORKDIR /src

# Copy source, then build with -mod=mod so go resolves and records go.sum entries
# for build-required deps only (no committed go.sum in this repo). Avoids `go mod
# tidy`, which also pulls dependencies' test-only modules — one of which demands a
# newer Go toolchain than this builder.
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -mod=mod -ldflags="-s -w" -o /app ./...

# ---- final stage ----
FROM gcr.io/distroless/static:nonroot

COPY --from=build /app /app

EXPOSE 8000

ENV APP_PORT=8000

USER nonroot:nonroot

ENTRYPOINT ["/app"]
