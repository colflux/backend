from decimal import Decimal

from django.core.management.base import BaseCommand

from app.models import DatasetMetadata, EmissionRecord, EmissionSource, Gas, Region, Sector


class Command(BaseCommand):
    help = "Carga datos preliminares para demostrar el modelo GEI."

    def handle(self, *args, **options):
        dataset, _ = DatasetMetadata.objects.get_or_create(
            name="Inventario GEI preliminar",
            defaults={
                "source": "Datos de ejemplo para prototipo",
                "version": "0.1",
                "publication_year": 2026,
                "license": "Demo",
            },
        )
        country, _ = Region.objects.get_or_create(name="Colombia", region_type=Region.COUNTRY)
        regions = [
            Region.objects.get_or_create(name="Antioquia", code="05", region_type=Region.DEPARTMENT, parent=country)[0],
            Region.objects.get_or_create(name="Cundinamarca", code="25", region_type=Region.DEPARTMENT, parent=country)[0],
            Region.objects.get_or_create(name="Valle del Cauca", code="76", region_type=Region.DEPARTMENT, parent=country)[0],
        ]
        gases = {
            "CO2": Gas.objects.get_or_create(name="Dioxido de carbono", chemical_formula="CO2", defaults={"gwp_100": 1})[0],
            "CH4": Gas.objects.get_or_create(name="Metano", chemical_formula="CH4", defaults={"gwp_100": 27.2})[0],
            "N2O": Gas.objects.get_or_create(name="Oxido nitroso", chemical_formula="N2O", defaults={"gwp_100": 273})[0],
        }
        sectors = {
            "Energia": Sector.objects.get_or_create(name="Energia", defaults={"ipcc_code": "1"})[0],
            "Agricultura": Sector.objects.get_or_create(name="Agricultura", defaults={"ipcc_code": "3"})[0],
            "Residuos": Sector.objects.get_or_create(name="Residuos", defaults={"ipcc_code": "5"})[0],
        }
        sources = {
            "Combustion estacionaria": EmissionSource.objects.get_or_create(name="Combustion estacionaria", sector=sectors["Energia"])[0],
            "Fermentacion enterica": EmissionSource.objects.get_or_create(name="Fermentacion enterica", sector=sectors["Agricultura"])[0],
            "Disposicion de residuos": EmissionSource.objects.get_or_create(name="Disposicion de residuos", sector=sectors["Residuos"])[0],
        }
        rows = [
            (2021, regions[0], sectors["Energia"], sources["Combustion estacionaria"], gases["CO2"], "124000.0", "124000.0"),
            (2022, regions[0], sectors["Agricultura"], sources["Fermentacion enterica"], gases["CH4"], "8200.0", "223040.0"),
            (2023, regions[0], sectors["Residuos"], sources["Disposicion de residuos"], gases["CH4"], "4100.0", "111520.0"),
            (2021, regions[1], sectors["Energia"], sources["Combustion estacionaria"], gases["CO2"], "98000.0", "98000.0"),
            (2022, regions[1], sectors["Agricultura"], sources["Fermentacion enterica"], gases["N2O"], "420.0", "114660.0"),
            (2023, regions[1], sectors["Residuos"], sources["Disposicion de residuos"], gases["CH4"], "3900.0", "106080.0"),
            (2021, regions[2], sectors["Energia"], sources["Combustion estacionaria"], gases["CO2"], "76000.0", "76000.0"),
            (2022, regions[2], sectors["Agricultura"], sources["Fermentacion enterica"], gases["CH4"], "6100.0", "165920.0"),
            (2023, regions[2], sectors["Residuos"], sources["Disposicion de residuos"], gases["N2O"], "210.0", "57330.0"),
        ]
        created = 0
        for year, region, sector, source, gas, value, co2e in rows:
            _, was_created = EmissionRecord.objects.get_or_create(
                dataset=dataset,
                region=region,
                sector=sector,
                source=source,
                gas=gas,
                year=year,
                defaults={
                    "value_tonnes": Decimal(value),
                    "co2e_tonnes": Decimal(co2e),
                    "method": "Factor de conversion PCG 100 anos",
                    "data_quality": EmissionRecord.ESTIMATED,
                },
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Datos GEI listos. Registros nuevos: {created}"))
