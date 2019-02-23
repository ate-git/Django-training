from django.shortcuts import render
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_extensions.mixins import CacheResponseMixin

from .models import Area
from .serializers import AreaSerializer, SubsAreaSerializer


# Create your views here.
class AreasViewSet(CacheResponseMixin, ReadOnlyModelViewSet):
    """省市区查询视图集"""

    pagination_class = None  # 禁用分页

    # queryset = Area.objects.filter(parent_id=None)
    def get_queryset(self):
        if self.action == 'list':  # 如果是list行为表示要所有省的模型
            return Area.objects.filter(parent_id=None)
        else:
            return Area.objects.all()

    # serializer_class = AreaSerializer
    def get_serializer_class(self):
        if self.action == 'list':
            return AreaSerializer
        else:
            return SubsAreaSerializer
