# syntax=docker/dockerfile:1

# FrankenPHP: a production-grade PHP app server (built on Caddy) for Laravel.
# Used together with Laravel Octane in worker mode for high throughput.
# https://hub.docker.com/r/dunglas/frankenphp
FROM dunglas/frankenphp:1-php8.3

# Install the PHP extensions Laravel + Postgres + Octane need.
# install-php-extensions ships with the FrankenPHP image.
RUN install-php-extensions \
        pdo_pgsql \
        pgsql \
        intl \
        opcache \
        zip \
        pcntl

# Composer (copied from the official Composer image).
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

ENV COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1

# Composer 2.8 hard-fails dependency resolution when any selected version has an
# open security advisory ("block-insecure"). All current laravel/framework 11.x
# releases carry advisories, so disable blocking to allow the build to resolve.
RUN composer config --global audit.block-insecure false

WORKDIR /app

# The FrankenPHP image ships a default /app/public/index.php; create-project
# refuses a non-empty target, so clear it first.
RUN rm -rf /app/public /app/* /app/.[!.]* 2>/dev/null || true

# 1) Create a fresh Laravel 11 skeleton. This pulls all framework deps from
#    Packagist at build time (network required during `docker build`).
RUN composer create-project --no-progress --prefer-dist "laravel/laravel:^11.0" .

# 2) Add Laravel Octane (FrankenPHP runtime).
RUN composer require --no-progress laravel/octane

# 3) Overlay the minimal source we author (routes, controller, db config).
COPY routes/web.php       /app/routes/web.php
COPY app/Http/Controllers/BenchmarkController.php /app/app/Http/Controllers/BenchmarkController.php
COPY config/database.php  /app/config/database.php

# 4) Install Octane wired to the FrankenPHP runtime, build a non-interactive
#    .env, and generate the app key. Runtime DB_* env vars (injected by compose)
#    are read by config/database.php via env() at boot.
RUN php artisan octane:install --server=frankenphp \
    && cp .env.example .env \
    && sed -i 's/^APP_ENV=.*/APP_ENV=production/' .env \
    && sed -i 's/^APP_DEBUG=.*/APP_DEBUG=false/' .env \
    && sed -i 's/^DB_CONNECTION=.*/DB_CONNECTION=pgsql/' .env \
    `# Laravel 11 defaults session/cache/queue to the database; the benchmark DB` \
    `# only has a 'users' table, so use non-DB drivers (the web middleware reads` \
    `# the session on every request, which would otherwise 500 even on /health).` \
    && sed -i 's/^SESSION_DRIVER=.*/SESSION_DRIVER=array/' .env \
    && sed -i 's/^CACHE_STORE=.*/CACHE_STORE=array/' .env \
    && sed -i 's/^QUEUE_CONNECTION=.*/QUEUE_CONNECTION=sync/' .env \
    && php artisan key:generate --force

# 5) Cache routes for production performance, optimize the autoloader, and make
#    storage writable. Config is intentionally NOT cached so DB_* env vars stay
#    dynamic at container start.
RUN php artisan route:cache \
    && composer dump-autoload --optimize \
    && chmod -R 775 storage bootstrap/cache

# Production OPcache + JIT tuning for the benchmark.
RUN { \
        echo 'opcache.enable=1'; \
        echo 'opcache.enable_cli=1'; \
        echo 'opcache.memory_consumption=256'; \
        echo 'opcache.interned_strings_buffer=32'; \
        echo 'opcache.max_accelerated_files=20000'; \
        echo 'opcache.validate_timestamps=0'; \
        echo 'opcache.jit=tracing'; \
        echo 'opcache.jit_buffer_size=128M'; \
    } > "$PHP_INI_DIR/conf.d/zz-opcache.ini"

ENV APP_PORT=8000

EXPOSE 8000

# Serve Laravel via Octane on the FrankenPHP runtime in worker mode.
# Persistent PDO connections (config/database.php) are reused across requests
# within each long-lived worker.
CMD ["php", "artisan", "octane:start", \
     "--server=frankenphp", \
     "--host=0.0.0.0", \
     "--port=8000"]
