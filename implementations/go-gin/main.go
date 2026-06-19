package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// httpClient is shared so the connection pool is reused across /aggregate fan-outs.
// The default Transport keeps only 2 idle connections per host, which forces heavy
// connection churn under a concurrent fan-out and causes intermittent failures.
// Raise the idle pool so keep-alive connections are reused like a real service.
var httpClient = &http.Client{
	Timeout: 10 * time.Second,
	Transport: &http.Transport{
		MaxIdleConns:        200,
		MaxIdleConnsPerHost: 200,
		MaxConnsPerHost:     200,
		IdleConnTimeout:     90 * time.Second,
	},
}

// User is the row shape for GET /users/:id.
// created_at is a time.Time so encoding/json serializes it as RFC3339.
type User struct {
	ID        int       `json:"id"`
	Name      string    `json:"name"`
	Email     string    `json:"email"`
	CreatedAt time.Time `json:"created_at"`
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func buildDSN() string {
	host := env("DB_HOST", "postgres")
	port := env("DB_PORT", "5432")
	name := env("DB_NAME", "benchmark")
	user := env("DB_USER", "benchmark")
	password := env("DB_PASSWORD", "benchmark")
	return fmt.Sprintf(
		"postgres://%s:%s@%s:%s/%s?sslmode=disable",
		user, password, host, port, name,
	)
}

func main() {
	gin.SetMode(gin.ReleaseMode)

	dsn := buildDSN()
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		log.Fatalf("failed to create connection pool: %v", err)
	}
	defer pool.Close()

	// Retry ping loop (~30s) so a brief DB startup delay does not crash the app.
	deadline := time.Now().Add(30 * time.Second)
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		pingErr := pool.Ping(ctx)
		cancel()
		if pingErr == nil {
			log.Println("connected to postgres")
			break
		}
		if time.Now().After(deadline) {
			log.Fatalf("could not reach postgres within 30s: %v", pingErr)
		}
		log.Printf("waiting for postgres: %v", pingErr)
		time.Sleep(1 * time.Second)
	}

	r := gin.New()
	r.Use(gin.Recovery())

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	r.GET("/serialize", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"id":    123,
			"name":  "John Doe",
			"email": "john@example.com",
		})
	})

	r.GET("/users/:id", func(c *gin.Context) {
		id, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
			return
		}

		var u User
		err = pool.QueryRow(
			c.Request.Context(),
			"SELECT id, name, email, created_at FROM users WHERE id = $1",
			id,
		).Scan(&u.ID, &u.Name, &u.Email, &u.CreatedAt)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
				return
			}
			log.Printf("query error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
			return
		}

		c.JSON(http.StatusOK, u)
	})

	r.GET("/cpu/:rounds", func(c *gin.Context) {
		rounds, err := strconv.Atoi(c.Param("rounds"))
		if err != nil || rounds <= 0 {
			c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
			return
		}
		if rounds > 10000000 {
			rounds = 10000000
		}

		sum := sha256.Sum256([]byte("backend-decision-lab"))
		for i := 1; i < rounds; i++ {
			sum = sha256.Sum256(sum[:])
		}

		c.JSON(http.StatusOK, gin.H{
			"rounds": rounds,
			"hash":   hex.EncodeToString(sum[:]),
		})
	})

	r.GET("/aggregate", func(c *gin.Context) {
		const requests = 10
		url := os.Getenv("UPSTREAM_URL") + "/delay/0.05"

		var succeeded int64
		var wg sync.WaitGroup
		wg.Add(requests)

		start := time.Now()
		for i := 0; i < requests; i++ {
			go func() {
				defer wg.Done()
				resp, err := httpClient.Get(url)
				if err != nil {
					return
				}
				defer resp.Body.Close()
				io.Copy(io.Discard, resp.Body)
				if resp.StatusCode == http.StatusOK {
					atomic.AddInt64(&succeeded, 1)
				}
			}()
		}
		wg.Wait()
		tookMs := int(time.Since(start).Milliseconds())

		c.JSON(http.StatusOK, gin.H{
			"requests":  requests,
			"succeeded": int(succeeded),
			"took_ms":   tookMs,
		})
	})

	port := env("APP_PORT", "8000")
	addr := ":" + port
	log.Printf("listening on %s", addr)
	if err := r.Run(addr); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
