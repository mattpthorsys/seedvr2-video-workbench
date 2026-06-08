docker compose --profile test build backend-tests frontend-tests
docker compose --profile test run --rm backend-tests
docker compose --profile test run --rm frontend-tests
