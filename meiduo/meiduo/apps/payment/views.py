from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from alipay import AliPay
from django.conf import settings
import os

from orders.models import OrderInfo
from .models import Payment


# Create your views here.
# 1.生成支付宝登录url

class PaymentView(APIView):
    """生成支付宝登录url"""
    permission_classes = [IsAuthenticated]  # 必须是登录用户才能访问此视图

    def get(self, request, order_id):
        # 获取当前登录用户
        user = request.user
        try:
            # 校验订单编号
            order = OrderInfo.objects.get(order_id=order_id, user=user, status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'])
        except OrderInfo.DoesNotExist:
            return Response({'message': '订单信息有误'}, status=status.HTTP_400_BAD_REQUEST)
        """
        # 支付宝
        ALIPAY_APPID = '2016091900551154'
        ALIPAY_DEBUG = True
        ALIPAY_URL = 'https://openapi.alipaydev.com/gateway.do'
        """
        # 创建alipay支付对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/app_private_key.pem'),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )

        # 调用它里面的方法 生成支付宝登录url后面的 查询参数部分
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 美多商城订单编号
            total_amount=str(order.total_amount),  # 注意: 一定要把总价转换成字符串类型,不然会报错
            subject='美多商城%s' % order_id,  # 注意:如果变量是字条串类型必须用%s占位,如果变量是int类型可以用%d也可以用%s占位
            return_url="http://www.meiduo.site:8080/pay_success.html",  # 支付成功后的回调url
        )
        # 拼接完整 支付宝登录url
        # 沙箱环境 : 	https://openapi.alipaydev.com/gateway.do? + 查询参数部分

        # 真实环境 : 	https://openapi.alipay.com/gateway.do? + 查询参数部分  order_id=xxx&a=xxx
        alipay_url = settings.ALIPAY_URL + '?' + order_string

        return Response({'alipay_url': alipay_url})

# 2.支付成功后的验证和修改订单状态 保存订单及支付流水号
class PaymentStatusView(APIView):

    def put(self, request):

        # 获取查询参数中的所有数据 query_params  /django  GET
        query_dict = request.query_params
        # 把query_dict类型对象转换成字典
        data = query_dict.dict()
        # 把查询参数中的sign签名部分数据单独提取出
        sign = data.pop('sign')
        # 创建alipay支付对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/app_private_key.pem'),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )
        # 调用alipay中的verify方法进行验证支付信息
        success = alipay.verify(data, sign)  # 如果返回True表示支付成功,如果False表示支付中信息有错误
        if success:
            # 获取美多订单编号
            order_id = data.get('out_trade_no')
            # 支付宝交易流水号
            trade_id = data.get('trade_no')
            # 把交易号和订单编号进行绑定存储
            Payment.objects.create(
                order_id=order_id,
                trade_id=trade_id
            )

            # 修改订单状态
            OrderInfo.objects.filter(order_id=order_id, status=OrderInfo.ORDER_STATUS_ENUM['UNPAID']).update(status=OrderInfo.ORDER_STATUS_ENUM['UNSEND'])

            return Response({'trade_id': trade_id})
        else:
            return Response({'message': '非法请求'}, status=status.HTTP_403_FORBIDDEN)


