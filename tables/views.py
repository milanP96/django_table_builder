import json

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, mixins
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from tables.models import DynamicTable
from tables.serializers import DynamicTableSerializer, CreateRowsSerializer
from tables.table_creator import TableCreatorException, TableCreator
from django.core import serializers as django_serializers


class TableView(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = DynamicTable.objects.all()
    serializer_class = DynamicTableSerializer

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        table_creator = TableCreator(instance.model_name, delete=True, old_instance=instance)
        table_creator.set_fields(instance.columns)

        try:
            table_creator.make_migrations()
            table_creator.migrate()

            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TableCreatorException as e:
            """Handle table creator custom exception"""
            return Response(e, status=status.HTTP_400_BAD_REQUEST)


class CreateRowView(APIView):
    serializer_class = CreateRowsSerializer

    def post(self, request, pk):

        serializer = self.serializer_class(data=request.data)

        serializer.is_valid(raise_exception=True)

        try:
            dynamic_table = DynamicTable.objects.get(id=pk)
        except Exception as e:
            return Response(f"Missing model with id={pk}", status=status.HTTP_400_BAD_REQUEST)

        table_creator = TableCreator(table_name=dynamic_table.model_name)
        table_creator.set_fields(dynamic_table.columns)
        model = table_creator.get_model_class()

        try:
            # Perform bulk create
            instances = [model(**data) for data in serializer.validated_data['data']]
            instances = model.objects.bulk_create(instances)
        except Exception as e:
            return Response(
                f"Can not create rows for table {dynamic_table.model_name} because of: {e}",
                status=status.HTTP_400_BAD_REQUEST
            )

        serialized_data = django_serializers.serialize('json', instances)

        # Deserialize and load the data
        deserialized_data = [{"id": x["pk"], **x["fields"]} for x in json.loads(serialized_data)]

        return Response(
                deserialized_data,
                status=status.HTTP_201_CREATED
            )


class GetAllRowView(APIView):

    def get(self, request, pk):
        try:
            dynamic_table = DynamicTable.objects.get(id=pk)
        except Exception as e:
            return Response(f"Missing model with id={pk}", status=status.HTTP_400_BAD_REQUEST)

        table_creator = TableCreator(table_name=dynamic_table.model_name)
        table_creator.set_fields(dynamic_table.columns)
        model = table_creator.get_model_class()


        try:
            # Perform bulk create
            instances = model.objects.all()
        except Exception as e:
            return Response(
                f"Can not create rows for table {dynamic_table.model_name} because of: {e}",
                status=status.HTTP_400_BAD_REQUEST
            )

        serialized_data = django_serializers.serialize('json', instances)

        # Deserialize and load the data
        deserialized_data = [{"id": x["pk"], **x["fields"]} for x in json.loads(serialized_data)]

        return Response(
                deserialized_data,
                status=status.HTTP_201_CREATED
            )