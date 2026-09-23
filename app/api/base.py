from rest_framework import viewsets
from rest_framework.permissions import AllowAny


class DataPortalModelViewSet(viewsets.ModelViewSet):
    authentication_classes = []
    permission_classes = [AllowAny]
