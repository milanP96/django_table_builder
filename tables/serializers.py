from rest_framework import serializers
import jsonschema
from rest_framework.serializers import ModelSerializer

from tables.models import DynamicTable
from tables.table_creator import TableCreator, TableCreatorException


class DynamicTableSerializer(ModelSerializer):
    model_name = serializers.CharField(max_length=63, required=True)  # max name length for postgres table name
    columns = serializers.ListField(child=serializers.JSONField(
        default={"column_name": "name1", "column_type": "string"}), required=True
    )

    def validate_columns(self, value):
        # JSON schema
        sub_json_schema = {
            "type": "object",
            "properties": {
                "column_name": {"type": "string"},
                "column_type": {"type": "string", "enum": ["string", "number", "boolean"]},
            },
            "required": ["column_name", "column_type"]
        }

        # Check sub-JSONs against the schema
        for sub_json in value:
            try:
                jsonschema.validate(sub_json, sub_json_schema)
            except jsonschema.ValidationError as e:
                raise serializers.ValidationError(str(e))

        return value

    class Meta:
        model = DynamicTable
        fields = ('pk', 'model_name', 'columns',)

    def create(self, validated_data):
        # Create migrations and new instance of dynamic model and store it

        table_creator = TableCreator(validated_data['model_name'])
        table_creator.set_fields(validated_data['columns'])

        try:
            table_creator.make_migrations()
            table_creator.migrate()

            return super(DynamicTableSerializer, self).create(
                {
                    "model_name": table_creator.pascal_case(),
                    "columns":table_creator.fields
                 }
            )
        except TableCreatorException as e:
            """Handle table creator custom exception"""
            raise serializers.ValidationError(e)

    def update(self, instance, validated_data):
        """
        !!!ATTENTION!!!
        For this test we will use simpler version of update without interacting with user
        about rename fields and 'null' problem. So all fields will have also null=True and default=None
        And renaming models will result recreate tables

        Pros: It is simpler now for me, so I will spent less time on task :D
        Cons: All data from renamed columns will be deleted and new fields will have null value
        TODO handle it
        """
        table_creator = TableCreator(validated_data['model_name'], update=True, old_instance=instance)
        table_creator.set_fields(validated_data['columns'])

        try:
            table_creator.make_migrations()
            table_creator.migrate()

            return super(DynamicTableSerializer, self).update(
                instance,
                {
                    "model_name": table_creator.pascal_case(),
                    "columns": table_creator.fields
                }
            )
        except TableCreatorException as e:
            """Handle table creator custom exception"""
            raise serializers.ValidationError(e)


class CreateRowsSerializer(serializers.Serializer):
    data = serializers.ListField(child=serializers.JSONField())
