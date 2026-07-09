import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand

from app.api.catalogo.views import ENTIDADES_SEMILLA, GRUPOS_CATALOGO, TIPO_MAP, _semilla_rows


class Command(BaseCommand):
    help = "Genera data-portal/assets/data/catalogo.json desde los modelos Django"

    def handle(self, *args, **options):
        grupos = []

        for grupo in GRUPOS_CATALOGO:
            entidades = []

            for nombre in grupo["entidades"]:
                try:
                    modelo_cls = apps.get_model("app", nombre)
                except LookupError:
                    continue

                campos = []
                for field in modelo_cls._meta.get_fields():
                    if field.is_relation and not hasattr(field, "column"):
                        continue
                    if field.name in ("id", "created_at", "updated_at"):
                        continue

                    tipo_raw = field.__class__.__name__
                    campo = {
                        "nombre": field.name,
                        "verbose_name": str(getattr(field, "verbose_name", field.name)),
                        "tipo": TIPO_MAP.get(tipo_raw, tipo_raw),
                        "tipo_raw": tipo_raw,
                        "requerido": not (
                            getattr(field, "blank", True) or getattr(field, "null", True)
                        ),
                        "max_length": getattr(field, "max_length", None),
                        "choices": [
                            {"valor": c[0], "etiqueta": c[1]}
                            for c in (getattr(field, "choices", None) or [])
                        ],
                        "es_fk": tipo_raw == "ForeignKey",
                        "modelo_fk": (
                            field.related_model.__name__
                            if tipo_raw == "ForeignKey"
                            else None
                        ),
                    }
                    campos.append(campo)

                entry = {
                    "nombre": nombre,
                    "verbose_name": str(modelo_cls._meta.verbose_name),
                    "verbose_name_plural": str(modelo_cls._meta.verbose_name_plural),
                    "total_campos": len(campos),
                    "campos": campos,
                }
                if nombre in ENTIDADES_SEMILLA:
                    entry["datos_semilla"] = _semilla_rows(modelo_cls)
                entidades.append(entry)

            grupos.append(
                {"nombre": grupo["nombre"], "icono": grupo["icono"], "entidades": entidades}
            )

        data = {"grupos": grupos}

        output = settings.BASE_DIR / "data-portal" / "assets" / "data" / "catalogo.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        total = sum(len(g["entidades"]) for g in grupos)
        self.stdout.write(
            self.style.SUCCESS(f"Catálogo generado: {total} entidades → {output}")
        )
