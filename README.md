# [Тестовое задание: Асинхронный сервис процессинга платежей](./task.md)

В тестовом задании не было сказано про отдельный сервис publisher. Этот функционал можно было реализовать в API, но тогда при нескольких репликах API было бы столько же и publisher'ов — все бы читали одни и те же pending-записи из outbox и публиковали дубли. Это создаст лишнюю нагрузку на брокер и усложнит отладку.

Публиковать в брокер точечно после записи в БД — сомнительно: это 2 операции (запись в Postgres + публикация в RabbitMQ). Они не атомарны. Если БД закоммитилась, а брокер не ответил — событие потеряно. Нужна гарантия, что оно не потеряется.

Поэтому всё равно нужен фоновый процесс, который читает outbox и ретраит публикацию. Раз он нужен — логичнее вынести его в отдельный сервис: не дублируется при масштабировании API, не блокирует HTTP-запросы, не смешивает логи. Publisher раз в 2 секунды забирает пачку pending-событий и публикует их в RabbitMQ. Это и есть outbox pattern.

У api, publisher, consumer свой пул подключений к субд. В pg_stat_activity отрисовывются реальные application_name. Можно смотреть какой сервис какие запросы делает. Можно было сделать чтобы publisher, consumer работали с данными через апишку, но это накладные расходы, эффективнее всего получить это напрямую из БД.

Я не стал делать env.example нарочно. Забрали проект - запустили. Если нет конфликта по проброшенным портам то всё включится одной командой вообще без настроек.

## Деплой
- Настроить проброс портов в docker-compose.yaml или в .env.docker
- Задепоить 
    ```bash 
    docker-compose up -d
    ```

## Развернётся 7 контейнеров

- payments_postgres
- payments_rabbitmq
- payments_migrate (Этот отработает и выключится)
- payments_api
- payments_consumer
- payments_mock_webhook
- payments_publisher

Никакой особой настройки Postgres и Rabbitmq не делал. Просто сервисы из коробки. 

Для оставшихся контейнеров собирал образ сам. Один образ под все сервисы. [Dockerfile](./Dockerfile)

## API
Доступен свагер http://127.0.0.1:8000/docs

Или ручками:
### Создание платежа
POST
```bash
curl --location 'http://127.0.0.1:8000/api/v1/payments' \
--header 'x-api-key: arisha-super-secret-api-key' \
--header 'Idempotency-Key: 136' \
--header 'Content-Type: application/json' \
--data '{
  "amount": "100.50",
  "currency": "RUB",
  "description": "Оплата заказа №42",
  "meta": {
    "order_id": "42",
    "user_id": "user-123"
  },
  "webhook_url": "http://mock-webhook:9000/webhook"}'
```
Ответ
```json
{
    "payment_id": "344ff39e-6720-4751-9f28-d86da84a644e",
    "status": "pending",
    "created_at": "2026-10-06T10:54:57.983458Z"
}
```
### Просмотр платежа
GET
```bash
curl --location 'http://127.0.0.1:8000/api/v1/payments/cbdb6406-a767-4513-ad3b-d46c40738d99' --header 'x-api-key: arisha-super-secret-api-key'
```
Ответ
```json
{
    "id": "cbdb6406-a767-4513-ad3b-d46c40738d99",
    "amount": "100.50",
    "currency": "RUB",
    "description": "Оплата заказа №42",
    "meta": {
        "user_id": "user-123",
        "order_id": "42"
    },
    "status": "succeeded",
    "idempotency_key": "123",
    "webhook_url": "https://example.com/hook",
    "created_at": "2026-10-05T16:15:08.681949Z",
    "processed_at": "2026-10-06T07:40:46.959626Z"
}
```



## [Publisher](app\outbox\publisher.py)
Каждые 2 секунды смотрит таблицу outbox и забирает пачку из 100 необработанных сообщений.
И публикует в очередь payments.new 

## [Consumer](app\consumer\worker.py)
Подписан на payments.new. Обрабатывает платёж ([в заглушке](app\consumer\processor.py)), отправляет вебхук (я замокал [сервис](app\mock_webhook.py), который отвечает двести в 90% случаев в логах видно что в него уходит), обновляет статус платежа в постгресе.



