from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, generics, authentication, permissions

from users.models import User
from users.serializers import UserSerializer


class ManageUserView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated user"""
    serializer_class = UserSerializer
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user