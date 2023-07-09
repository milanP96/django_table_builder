from drf_spectacular.utils import extend_schema
from drf_spectacular.extensions import OpenApiViewExtension


class CustomOpenApiViewExtension(OpenApiViewExtension):
    target_class = extend_schema  # apply this extension to all `extend_schema` decorators

    def view_replacement(self):
        self.target_class(
            request=extend_schema(
                description='',
                responses={},
                request={'media': 'application/json'},
            ),
        )


def postprocess_hook(*args, **kwargs):
    CustomOpenApiViewExtension().decorate_operations(*args, **kwargs)
