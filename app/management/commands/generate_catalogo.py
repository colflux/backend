from django.conf import settings
from django.core.management.base import BaseCommand

from app.catalogo.generator import escribir_catalogo_assets


class Command(BaseCommand):
    help = "Genera docs/assets/data/catalogo.json, catalogo.js y colflux.dbml desde los modelos Django"

    def handle(self, *args, **options):
        output_dir = settings.BASE_DIR / "docs" / "assets" / "data"
        data, json_out, js_out, dbml_out = escribir_catalogo_assets(output_dir)
        total = sum(len(g["entidades"]) for g in data["grupos"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo generado: {total} entidades → {json_out}, {js_out} y {dbml_out}"
            )
        )
