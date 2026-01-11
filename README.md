# CoinMrkt

A web application for buying and selling precious metal coins (gold, silver, etc.).

## Prerequisites

- Docker and Docker Compose

## Running Locally

1. Clone the repository
2. Start the application:
   ```bash
   docker compose up --build
   ```
3. Open http://localhost:8000 in your browser

## Stopping

```bash
docker compose down
```

To also remove the database data:
```bash
docker compose down -v
```

## Services

| Service | URL                   |
|---------|-----------------------|
| App     | http://localhost:8000 |
| MongoDB | localhost:27017       |

## API

- `GET /api/coins` - List all coins
- `POST /api/coins` - Create a coin
- `GET /api/coins/{id}` - Get a coin
- `DELETE /api/coins/{id}` - Delete a coin
- `GET /api/orders` - List all orders
- `POST /api/orders` - Create an order
# agentplatz
