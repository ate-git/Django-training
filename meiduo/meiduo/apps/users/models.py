from django.db import models
from django.contrib.auth.models import AbstractUser
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, BadData
from django.conf import settings
from meiduo.utils.models import BaseModel
# Create your models here.


class User(AbstractUser):
    """自定义用户模型"""
    mobile = models.CharField(verbose_name='手机号', max_length=11, unique=True)
    email_active = models.BooleanField(verbose_name='邮箱状态', default=False)
    default_address = models.ForeignKey('Address', related_name='users', null=True, blank=True,
                                        on_delete=models.SET_NULL, verbose_name='默认地址')

    class Meta:
        db_table = 'tb_user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name


    def generate_verify_email_url(self):
        """生成激活url"""
        # 1.创建加密的序列化器对象
        serializer = Serializer(settings.SECRET_KEY, 24 * 60 * 60)
        # 2. 包装一个要加密的字典数据
        data = {'user_id': self.id, 'email': self.email}
        # 3. 调用dumps方法加密
        token = serializer.dumps(data).decode()

        # 4. 拼接好verify_url并响应
        return 'http://www.meiduo.site:8080/success_verify_email.html?token=' + token

    @staticmethod
    def check_verify_email_token(token):
        """token解密及查询user"""
        # 1.创建加密的序列化器对象
        serializer = Serializer(settings.SECRET_KEY, 24 * 60 * 60)
        # 2. 调用loads方法对token解密
        try:
            data = serializer.loads(token)
        except BadData:
            return None
        else:
            # 3. 取出user_id和 email 然后用这两个字段查到唯一的那个用户
            user_id = data.get('user_id')
            email = data.get('email')
            try:
                user = User.objects.get(id=user_id, email=email)
            except User.DoesNotExist:
                return None
            else:
                return user


class Address(BaseModel):
    """
    用户地址
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses', verbose_name='用户')
    title = models.CharField(max_length=20, verbose_name='地址名称')
    receiver = models.CharField(max_length=20, verbose_name='收货人')
    province = models.ForeignKey('areas.Area', on_delete=models.PROTECT, related_name='province_addresses', verbose_name='省')
    city = models.ForeignKey('areas.Area', on_delete=models.PROTECT, related_name='city_addresses', verbose_name='市')
    district = models.ForeignKey('areas.Area', on_delete=models.PROTECT, related_name='district_addresses', verbose_name='区')
    place = models.CharField(max_length=50, verbose_name='地址')
    mobile = models.CharField(max_length=11, verbose_name='手机')
    tel = models.CharField(max_length=20, null=True, blank=True, default='', verbose_name='固定电话')
    email = models.CharField(max_length=30, null=True, blank=True, default='', verbose_name='电子邮箱')
    is_deleted = models.BooleanField(default=False, verbose_name='逻辑删除')

    class Meta:
        db_table = 'tb_address'
        verbose_name = '用户地址'
        verbose_name_plural = verbose_name
        ordering = ['-update_time']