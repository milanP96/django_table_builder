from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import Field, JSONField


class ColumnsField(ArrayField):
    """Custom field for columns in table model"""

    def __init__(self, base_field: Field, max_columns: int = 1600, **kwargs):
        self.max_columns = max_columns
        super().__init__(base_field, **kwargs)

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        if self.max_columns and len(value) > self.max_columns:
            raise ValidationError(f"Exceeded maximum number of columns ({self.max_elements}) for ArrayField.")


class DynamicTable(models.Model):
    model_name = models.CharField(max_length=63, unique=True)  # max table name length for postgres
    columns = ColumnsField(
        base_field=JSONField(),
        max_columns=1600,  # max number of columns per table
        blank=False,
        null=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def lower_name(self):
        return self.model_name.lower()

