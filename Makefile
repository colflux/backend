DUMP_FILE=data/dump.sql

db-dump:
	docker compose exec db pg_dump -U ghg ghg > $(DUMP_FILE)
	@echo "✓ Dump guardado en $(DUMP_FILE)"

db-restore:
	docker compose down -v
	docker compose up -d db
	@echo "Esperando que Postgres esté listo..."
	@until docker compose exec db pg_isready -U ghg -d ghg; do sleep 1; done
	docker compose exec -T db psql -U ghg ghg < $(DUMP_FILE)
	@echo "✓ Base de datos restaurada"
