from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_redis import get_redis_connection
from decimal import Decimal
from rest_framework.generics import CreateAPIView
from rest_framework import status

# Create your views here.
from goods.models import SKU
from .serializer import OrderSettlementSerializer, CommitOrderSerializer, UncommentsSerializer, CommentsSerializer, \
    GetCommentsSerializer
from .models import OrderGoods, OrderInfo


class GetCommentsView(APIView):
    """获取商品详情页评论信息"""

    def get(self, request, pk):

        skus = OrderGoods.objects.filter(sku_id=pk).order_by('-update_time')

        for sku in skus:
            order_info = sku.order
            user = order_info.user
            if sku.is_anonymous:
                name = user.username
            else:
                name = '匿名用户'

            sku.username = name

        serializer = GetCommentsSerializer(skus, many=True)

        return Response(serializer.data)


class UncommentsView(APIView):
    # 登录认证
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """查询未评论的商品"""
        goods = OrderGoods.objects.filter(order_id=pk, is_commented=0)

        serializer = UncommentsSerializer(goods, many=True)

        return Response(serializer.data)

    def post(self, request, pk):
        """保存评论信息"""
        sku_id = request.data.get('sku')
        try:
            goods = OrderGoods.objects.get(order_id=pk, sku_id=sku_id)
        except Exception:
            return Response({'message': '获取订单商品信息失败'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CommentsSerializer(goods, data=request.data)

        serializer.is_valid(raise_exception=True)

        serializer.save()
        # 更新订单状态
        if OrderGoods.objects.filter(order_id=pk, is_commented=0):
            pass
        else:
            OrderInfo.objects.filter(order_id=pk, status=OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT']).update(
                status=OrderInfo.ORDER_STATUS_ENUM["FINISHED"])

        return Response({'message': 'ok'})


class CommitOrderView(CreateAPIView):
    """保存商品"""
    # 校验权限
    permission_classes = [IsAuthenticated]

    # 指定序列化器
    serializer_class = CommitOrderSerializer


class OrderSettlementView(APIView):
    """结算订单视图"""
    # 设置权限
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取购物车中用户勾选的商品信息"""
        user = request.user
        redis_conn = get_redis_connection('cart')
        # 根据用户id到数据库查询商品信息和勾选信息
        redis_cart = redis_conn.hgetall("cart_%s" % user.id)
        selected_cart = redis_conn.smembers("selected_%s" % user.id)

        cart = {}  # 用于存放勾选商品的字典
        for sku_id in selected_cart:
            cart[int(sku_id)] = int(redis_cart[sku_id])  # 创建id:count键值对

        # 查询商品信息
        skus = SKU.objects.filter(id__in=cart.keys())
        # 遍历skus, 给每个sku增加count属性
        for sku in skus:
            sku.count = cart[sku.id]

        # 运费
        freight = Decimal('10.00')

        # 创建序列化对象
        serializer = OrderSettlementSerializer({'freight': freight, 'skus': skus})

        return Response(serializer.data)
