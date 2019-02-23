from django.shortcuts import render
from rest_framework.views import APIView
from QQLoginTool.QQtool import OAuthQQ
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
import logging
from rest_framework_jwt.settings import api_settings

from .models import QQAuthUser
from .utils import generate_save_user_token
from .serializers import QQAuthUserSerializer
from carts.utils import merge_cart_cookie_to_redis


logger = logging.getLogger('django')

# Create your views here.
class QQAuthUserView(APIView):
    """扫码成功后回调处理"""

    def get(self, request):
        # 1.获取查询参数中的code参数
        code = request.query_params.get('code')
        if not code:
            return Response({'message': '缺少code'}, status=status.HTTP_400_BAD_REQUEST)
        # 1.1 创建qq登录工具对象
        oauthqq = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                          client_secret=settings.QQ_CLIENT_SECRET,
                          redirect_uri=settings.QQ_REDIRECT_URI)
        try:
            # 2.通过code向QQ服务器请求获取access_token
            access_token = oauthqq.get_access_token(code)
            # 3.通过access_token向QQ服务器请求获取openid
            openid = oauthqq.get_open_id(access_token)
        except Exception as error:
            logger.info(error)
            return Response({'message': 'QQ服务器异常'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            # 4.查询openid是否绑定过美多商城中的用户
            qqauth_model = QQAuthUser.objects.get(openid=openid)
        except QQAuthUser.DoesNotExist:
            # 如果openid没有绑定过美多商城中的用户
            # 把openid进行加密安全处理,再响应给浏览器,让它先帮我们保存一会
            openid_sin = generate_save_user_token(openid)
            return Response({'access_token': openid_sin})

        else:
            # 如果openid已经绑定过美多商城中的用户(生成jwt token直接让它登录成功)
            # 手动生成token

            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
            # 获取user对象
            user = qqauth_model.user
            payload = jwt_payload_handler(user)  # 生成载荷
            token = jwt_encode_handler(payload)  # 根据载荷生成token

            response = Response({
                'token': token,
                'username': user.username,
                'user_id': user.id
            })
            # 做cookie购物车合并到redis操作
            merge_cart_cookie_to_redis(request, user, response)

            return response




    def post(self, request):

        # 创建序列化器对象,进行反序列化
        serializer = QQAuthUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # 手动生成jwt Token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
        # 获取user对象

        payload = jwt_payload_handler(user)  # 生成载荷
        token = jwt_encode_handler(payload)  # 根据载荷生成token

        response = Response({
            'token': token,
            'username': user.username,
            'user_id': user.id
        })
        # 做cookie购物车合并到redis操作
        merge_cart_cookie_to_redis(request, user, response)

        return response




class QQAuthURLView(APIView):
    """生成QQ扫码url"""

    def get(self, request):
        # 1.获取next(从那里去到login界面)参数路径
        next = request.query_params.get('next')
        if not next:  # 如果没有指定来源将来登录成功就回到首页
            next = '/'

        # QQ登录参数
        """
        QQ_CLIENT_ID = '101514053'
        QQ_CLIENT_SECRET = '1075e75648566262ea35afa688073012'
        QQ_REDIRECT_URI = 'http://www.meiduo.site:8080/oauth_callback.html'
        oauthqq = OAuthQQ(client_id='101514053', 
                  client_secret='1075e75648566262ea35afa688073012', 
                  redirect_uri='http://www.meiduo.site:8080/oauth_callback.html',
                  state=next)
        """

        # 2.创建QQ登录sdk 的对象
        oauthqq = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                          client_secret=settings.QQ_CLIENT_SECRET,
                          redirect_uri=settings.QQ_REDIRECT_URI,
                          state=next)
        # 3.调用它里面的get_qq_url方法来拿到拼接好的扫码链接
        login_url = oauthqq.get_qq_url()


        # 4.把扫码url响应给前端
        return Response({'login_url': login_url})