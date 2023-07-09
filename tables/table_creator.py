import os
import re
from io import StringIO
from typing import List

from django.apps import apps
from django.core.management import call_command
from django.core.management.utils import run_formatters
from django.db import ConnectionHandler, models
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState, ModelState
from django.db.migrations.writer import MigrationWriter

from tables.models import DynamicTable


class TableCreatorException(Exception):
    """Create some custom table exception functionality..."""
    def __init__(self, message):
        self.message = message
        super().__init__(f"Can not execute your request because of: {self.message}")


class TableCreator:

    def __init__(
            self, table_name: str, app_label: str = 'tables', update: bool = False,
            delete: bool = False, old_instance: DynamicTable = None
    ):
        self.app_label = app_label
        self.app_labels = set()
        self.app_labels.add(self.app_label)

        self.table_name = table_name
        self.fields = None

        connections = ConnectionHandler()
        self.connection = connections['default']

        self.message = StringIO()
        self.new_model = None
        self.written_files = list()

        self.update = update
        self.delete = delete
        self.old_instance = old_instance

        if delete and update:
            raise TableCreatorException("You can not give args delete and update as True. Please choose just one")

    def set_fields(self, fields: list):
        """Set fields from user input"""
        self.fields = fields

    def log_to_message(self, msg):
        """Write to StringIO message"""
        self.message.write(msg)

    def create_fields(self, columns: List[dict] = None):
        fields = dict()

        if self.update:
            fields['id'] = models.BigAutoField(primary_key=True)

        for field in self.fields if columns is None else columns:
            fields[field['column_name']] = self.get_field_class(field_type=field['column_type'])

        return fields

    def get_dynamic_model(self, model_name: str, columns: List[dict]):
        meta = type('Meta', (), {'app_label': self.app_label})
        attrs = {'__module__': f'{self.app_label}.models', 'Meta': meta}

        fields = self.create_fields(columns=columns)

        for field_name, field_type in fields.items():
            attrs[field_name] = field_type

        dynamic_model = type(model_name, (models.Model,), attrs)

        return dynamic_model

    def create_dynamic_model(self):
        """This function is creating dynamic model for tables app"""

        meta = type('Meta', (), {'app_label': self.app_label})

        attrs = {'__module__': f'{self.app_label}.models', 'Meta': meta}

        fields = self.create_fields()

        for field_name, field_type in fields.items():
            attrs[field_name] = field_type

        dynamic_model = type(self.pascal_case(), (models.Model,), attrs)

        return dynamic_model

    def pascal_case(self) -> str:
        """Model name convention is in pascal case, do we are converting
        user input to pascal case if it is not already"""

        x = self.table_name.split("_")
        parts = list()
        for _ in x:
            for part in re.sub( r"([A-Z])", r" \1", _).split():
                parts.append(part)

        res = []
        for i in parts:
            i = i.title()
            res.append(i)
        return "".join(res)

    def write_migration_files(self, changes: dict):
        """
        Take a changes dict and write them out as migration files.
        """
        directory_created = {}
        for app_label, app_migrations in changes.items():
            for migration in app_migrations:
                # Describe the migration
                writer = MigrationWriter(migration, True)

                # Write the migrations file to the disk.
                migrations_directory = os.path.dirname(writer.path)
                if not directory_created.get(app_label):
                    os.makedirs(migrations_directory, exist_ok=True)
                    init_path = os.path.join(migrations_directory, "__init__.py")
                    if not os.path.isfile(init_path):
                        open(init_path, "w").close()
                    # We just do this once per app
                    directory_created[app_label] = True
                migration_string = writer.as_string()
                with open(writer.path, "w", encoding="utf-8") as fh:
                    fh.write(migration_string)
                    self.written_files.append(writer.path)

        run_formatters(self.written_files)

    def name_lower(self) -> str:
        return self.table_name.replace(' ', '').replace('_', '').lower()

    def build_project_state(self) -> ProjectState:
        apps.clear_cache()
        app_models = {}

        for model in apps.get_models(include_swapped=True):
            model_state = ModelState.from_model(model)
            app_models[(model_state.app_label, model_state.name_lower)] = model_state

        queryset = list()  # dynamic models what we should keep after migration

        updated_name = self.update and self.old_instance.model_name != self.pascal_case()

        if self.delete or updated_name:
            queryset = DynamicTable.objects.exclude(model_name=self.old_instance.model_name)
        else:
            queryset = DynamicTable.objects.all()

        for existing_dynamic_model in queryset:
            app_models[(self.app_label, existing_dynamic_model.lower_name())] = \
                ModelState(
                    app_label=self.app_label,
                    name=existing_dynamic_model.model_name,
                    fields=self.create_fields()
                )

        if self.delete and app_models.get((self.app_label, self.name_lower())) is not None:
            del app_models[(self.app_label, self.name_lower())]

        app_config = apps.get_app_config(self.app_label)

        if self.delete and self.old_instance.lower_name() in app_config.models:
            del app_config.models[self.old_instance.lower_name()]

        if app_models.get((self.app_label, self.name_lower())) is not None and not self.update and not self.delete:
            raise TableCreatorException('Model is already created')

        if app_models.get((self.app_label, self.name_lower())) is None and self.update and not updated_name:
            raise TableCreatorException('Missing model. Please create new model and then you can update it')

        if queryset.count() == DynamicTable.objects.all().count() and self.delete:
            raise TableCreatorException('Missing model. You are trying to delete not existing model.')

        if self.update and not updated_name:
            edit_model_state = app_models.get((self.app_label, self.name_lower()))
            edit_model_state.fields = self.create_fields()
        elif not self.delete or updated_name:
            self.new_model = self.create_dynamic_model()
            app_models[(self.app_label, self.name_lower())] = ModelState.from_model(self.new_model)

        return ProjectState(app_models)

    def build_init_project_state(self) -> ProjectState:
        app_models = {}

        for model in apps.get_models(include_swapped=True):
            model_state = ModelState.from_model(model)
            app_models[(model_state.app_label, model_state.name_lower)] = model_state

        for existing_dynamic_model in DynamicTable.objects.all():
            app_models[(self.app_label, existing_dynamic_model.lower_name())] = \
                ModelState(
                    app_label=self.app_label,
                    name=existing_dynamic_model.model_name,
                    fields=self.create_fields(columns=existing_dynamic_model.columns)
                )

        return ProjectState(app_models)

    def make_migrations(self):
        """Create migrations files and models"""

        loader = MigrationLoader(None, ignore_no_migrations=True)

        loader.check_consistent_history(self.connection)

        questioner = NonInteractiveMigrationQuestioner(
            specified_apps=self.app_labels,
            dry_run=False,
            verbosity=1,
            log=self.log_to_message,
        )

        auto_detector = MigrationAutodetector(
            self.build_init_project_state(),
            self.build_project_state(),
            questioner,
        )

        changes = auto_detector.changes(
            graph=loader.graph,
            trim_to_apps=self.app_labels or None,
            convert_apps=self.app_labels or None,
            migration_name=None,
        )

        self.write_migration_files(changes)

    def get_model_class(self) -> models.Model:
        return self.new_model if self.new_model is not None else self.create_dynamic_model()  # return model class

    @staticmethod
    def migrate():
        call_command('migrate', 'tables')

    @staticmethod
    def get_field_class(field_type):
        field_classes = {  # null and default are added without interacting with user
            "string": models.TextField(null=True, default=None),
            "number": models.IntegerField(null=True, default=None),
            "boolean": models.BooleanField(null=True, default=None)
        }

        return field_classes[field_type]







