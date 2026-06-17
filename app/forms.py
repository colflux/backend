from django import forms

from .models import EmissionRecord


class EmissionRecordForm(forms.ModelForm):
    class Meta:
        model = EmissionRecord
        fields = [
            "dataset",
            "region",
            "sector",
            "source",
            "gas",
            "year",
            "value_tonnes",
            "co2e_tonnes",
            "unit",
            "method",
            "data_quality",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "method": forms.TextInput(attrs={"placeholder": "Ej. factor de emision IPCC"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
