# FinFlow — Бот отслеживания финансовых операций

Это Telegram‑бот для учёта финансовых операций, написанный на Python и Docker. Он поддерживает окружения разработки (dev) и продакшна (prod) с изолированными сетями и стеками для предотвращения конфликтов.

## Предварительные требования
- Установленные Docker и Docker Compose.
- Python 3.13.2 (для локальной разработки, при необходимости).

## Конфигурация
- `.env.dev`: параметры для разработки (Windows).
- `.env.prod`: параметры для продакшна (Linux/Docker).

## Запуск с нуля

### 1. Очистка существующих контейнеров, томов и образов
Для чистого старта удалите все контейнеры, тома, сети и образы, связанные с проектом:
```powershell
docker-compose -f docker-compose.dev.yml -p dev_finflow down -v
docker-compose -f docker-compose.prod.yml -p prod_finflow down -v
docker volume prune -f
docker network prune -f
docker image prune -a -f
```

### 2. Сборка и запуск окружения разработки
- PostgreSQL и Redis стартуют на портах из `.env.dev` (по умолчанию 5433 и 6380).
- Бот **не** запускается в dev.
- Используется отдельная сеть `dev_network` и имя стека `dev_finflow` для изоляции.
```powershell
docker-compose -f docker-compose.dev.yml -p dev_finflow --env-file .env.dev up -d --build
```
- Проверьте логи, чтобы убедиться, что окружение запущено:
  ```powershell
  docker logs dev_finflow_postgres_1
  docker logs dev_finflow_redis_1
  ```

### 3. Сборка и запуск окружения продакшна
- PostgreSQL, Redis и бот стартуют на портах из `.env.prod` (по умолчанию 5432 и 6379).
- Используется отдельная сеть `prod_network` и имя стека `prod_finflow` для изоляции.
```powershell
docker-compose -f docker-compose.prod.yml -p prod_finflow --env-file .env.prod up -d --build
```
- Проверьте логи:
  ```powershell
  docker logs prod_finflow_postgres_1
  docker logs prod_finflow_redis_1
  docker logs prod_finflow_bot_1
  ```

### 4. Одновременный запуск dev и prod
Вы можете запускать dev и prod параллельно в изолированных сетях:
```powershell
docker-compose -f docker-compose.dev.yml -p dev_finflow --env-file .env.dev up -d --build
docker-compose -f docker-compose.prod.yml -p prod_finflow --env-file .env.prod up -d --build
```
- Убедитесь в работе обоих, проверив логи соответствующих стеков.

### 5. Остановка и очистка
Чтобы остановить и удалить контейнеры конкретного окружения:
- dev:
  ```powershell
  docker-compose -f docker-compose.dev.yml -p dev_finflow down -v
  ```
- prod:
  ```powershell
  docker-compose -f docker-compose.prod.yml -p prod_finflow down -v
  ```
- Очистка неиспользуемых томов и сетей:
  ```powershell
  docker volume prune -f
  docker network prune -f
  ```

### Примечания
- Проверьте, что `.env.dev` и `.env.prod` содержат корректные учётные данные и порты.
- Бот запускается **только** в prod‑окружении.
- Часовой пояс по умолчанию — Europe/Moscow.
- Флаг `-p` задаёт уникальные имена стеков (`dev_finflow`, `prod_finflow`), избегая конфликтов.
- Флаг `--env-file` подгружает нужные переменные окружения.

## Решение проблем
- **Конфликт портов**: измените `POSTGRES_PORT` и `REDIS_PORT` в `.env.dev` и `.env.prod`.
- **Просмотр логов**: `docker logs <имя_контейнера>` (например, `docker logs dev_finflow_postgres_1`).
- **Проверка сетей**: убедитесь, что сети `dev_network` и `prod_network` созданы (`docker network ls`).

## Вклад
Присылайте issues и pull‑requests!
