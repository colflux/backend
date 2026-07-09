from rest_framework import status
from rest_framework.response import Response

from app.api.base import DataPortalModelViewSet
from app.api.reportador.serializers import ReportadorSerializer
from app.models import Reportador


class ReportadorViewSet(DataPortalModelViewSet):
    queryset = Reportador.objects.all()
    serializer_class = ReportadorSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = self.get_serializer(instance)
        response_status = status.HTTP_201_CREATED if getattr(serializer, "created", True) else status.HTTP_200_OK
        data = {**output.data, "created": getattr(serializer, "created", True)}
        return Response(data, status=response_status)
