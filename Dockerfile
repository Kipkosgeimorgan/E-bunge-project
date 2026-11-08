FROM php:8.3-cli-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libsqlite3-dev libonig-dev \
    && docker-php-ext-install pdo_sqlite sqlite3 mbstring \
    && apt-get purge -y --auto-remove libsqlite3-dev libonig-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app/
RUN mkdir -p /app/var/uploads && chown -R www-data:www-data /app/var
RUN printf 'upload_max_filesize=8M\npost_max_size=10M\n' > /usr/local/etc/php/conf.d/uploads.ini
ENV PORT=3000
EXPOSE 3000
USER www-data
CMD ["sh", "-c", "exec php -S 0.0.0.0:${PORT:-3000} -t /app/public /app/public/router.php"]
