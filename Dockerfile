
FROM php:8.3-cli-bookworm

# Install mbstring dependency
RUN apt-get update && apt-get install -y --no-install-recommends \
    libonig-dev \
    && docker-php-ext-install mbstring \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app/

# Verify SQLite extensions are available
RUN php -m | grep -i pdo_sqlite \
    && php -m | grep -i sqlite3

# Prepare application storage
RUN mkdir -p /app/var/uploads \
    && chown -R www-data:www-data /app/var

# PHP upload settings
RUN printf 'upload_max_filesize=8M\npost_max_size=10M\n' \
    > /usr/local/etc/php/conf.d/uploads.ini

ENV PORT=10000

EXPOSE 10000

USER www-data

CMD ["sh", "-c", "exec php -S 0.0.0.0:${PORT:-10000} -t /app/public /app/public/router.php"]

