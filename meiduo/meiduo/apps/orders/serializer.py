from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from django.db import transaction
from django_redis import get_redis_connection

from goods.models import SKU
from .models import OrderInfo, OrderGoods


class CommitOrderSerializer(serializers.ModelSerializer):
    """保存订单序列化器"""

    class Meta:
        model = OrderInfo
        fields = ['order_id', 'pay_method', 'address']
        # order_id只做输出,其余两个只做输入
        read_only_fields = ['order_id']
        extra_kwargs = {
            'address': {
                'write_only': True,
                'required': True,
                # 'error_messages':{
                #     "required": "请选择宝贝收货地址"
                # }
            },
            'pay_method': {
                'write_only': True,
                'required': True
            }
        }

    def create(self, validated_data):
        """重写序列化器的create方法,存储订单表"""
        # 注意存储订单表有4个表中的信息需要改动,这四个表的改动要么一起成功,要么一起失败,所以应该使用事物.
        # 获取user对象
        user = self.context['request'].user
        # 生成订单编号order_id  它由当前时间+用户id号组成
        # 注意导入timezone的时候,是从django的utils下导入的
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + "%09d" % user.id
        # 获取用户的收货地址
        address = validated_data.get('address')
        # 获取支付方式
        pay_method = validated_data.get('pay_method')

        # 根据支付方式修改订单状态 目前只有货到付款和支付宝付款两种方式
        # 如果选择货到付款,那么状态应该为待发货,如果是支付宝付款,那么状态应该是待支付
        # 使用三目运算符来判断
        status = (OrderInfo.ORDER_STATUS_ENUM['UNPAID']
                  if OrderInfo.PAY_METHODS_ENUM['ALIPAY'] == pay_method
                  else OrderInfo.ORDER_STATUS_ENUM['UNSEND'])

        with transaction.atomic():  # 开启事务,将需要修改数据库的操作都放在里面

            # 创建事务保存点,用于回滚到这个位置或者提交的时候从这个位置开始
            save_point = transaction.savepoint()

            try:
                # 保存订单的基本信息
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=0,
                    total_amount=Decimal('0.00'),
                    freight=Decimal('10.00'),
                    pay_method=pay_method,
                    status=status
                )

                # 从redis中取出用户勾选的商品信息
                redis_conn = get_redis_connection('cart')
                redis_cart_dict = redis_conn.hgetall('cart_%s' % user.id)
                redis_selected_ids = redis_conn.smembers('selected_%s' % user.id)

                # 如果没有勾选商品,不让跳转页面
                if not redis_selected_ids:
                    raise serializers.ValidationError('亲,你还没有选择宝贝哦~')
                # 将勾选的商品和商品数量放到一个新的字典中
                cart_dict = {}
                for selected_id in redis_selected_ids:
                    cart_dict[int(selected_id)] = int(redis_cart_dict[selected_id])

                # 遍历这个新的字典,然后对每个商品做保存处理
                for sku_id in cart_dict:

                    while True:
                        # 因为这里用到乐观锁处理资源竞争问题,第一次没有下单成功,并且商品数量充足的情况下,
                        # 让其一直下单购买,直到商品不足或者购买成功才退出循环.
                        # 获取sku_id对应的商品
                        sku = SKU.objects.get(id=sku_id)  # 因为这里面的代码都在一个try里面,如果查询失败就回滚到保存点
                        # 获取到这个商品的数量
                        sku_count = cart_dict[sku_id]

                        # 查询出这个商品原先的数量和销量
                        origin_stock = sku.stock
                        origin_sales = sku.sales

                        # 库存和本次要购买的数量做对比
                        if sku_count > origin_stock:
                            # 如果进入到里面,就说明库存不足,直接抛出异常
                            raise serializers.ValidationError('库存不足')

                        # 走到这里说明库存没有问题,可以开始下单了
                        # 计算新的库存和销量
                        new_stock = origin_stock - sku_count
                        new_sales = origin_sales + sku_count

                        # 再次查询这个商品的总数量,如果没有被修改,则可以将新数据更新回数据库
                        result = SKU.objects.filter(id=sku.id, stock=origin_stock).update(stock=new_stock,
                                                                                          sales=new_sales)

                        if not result:  # 如果没有查询出来数据,就更新不成功,将返回更新了0个数据,如果更新成功,返回非0
                            continue  # 结束本次循环,开始下一次循环

                        # 如果到这里,说明SKU数据已经更新成功,现在可以修改SPU表的销量了
                        spu = sku.goods  # 用外建来找到SPU对象
                        spu.sales += sku_count  # spu的销量和sku不一样,他是所有的sku销量加起来的
                        spu.save()

                        # 保存订单商品信息
                        OrderGoods.objects.create(
                            order=order,
                            sku=sku,
                            count=sku_count,
                            price=sku.price
                        )

                        # 累加计算总数量和总价
                        order.total_count += sku_count
                        order.total_amount += sku.price * sku_count

                        # 计算完成后跳出循环
                        break

                # 等循环完了后,把邮费加上
                order.total_amount += order.freight
                order.save()

            except Exception:
                # 暴力回滚,无论中间出现什么问题,都回滚到保存点
                transaction.savepoint_rollback(save_point)
                # 注意,回滚后一定要中断,不能让代码继续往下走.因为前端只要收到返回数据,就会显示下单成功
                raise
            else:
                # try中没有问题,就把数据提交到数据库
                transaction.savepoint_commit(save_point)

        # 到这里就说明订单保存成功,可以清除购物车中已经提交的商品
        pl = redis_conn.pipeline()
        pl.hdel('cart_%s' % user.id, *cart_dict)
        pl.srem('selected_%s' % user.id, *cart_dict)
        pl.execute()

        return order


class CartSKUSerializer(serializers.ModelSerializer):
    """
    购物车商品数据序列化器
    """
    count = serializers.IntegerField(label='数量')

    class Meta:
        model = SKU
        fields = ('id', 'name', 'default_image_url', 'price', 'count')


class OrderSettlementSerializer(serializers.Serializer):
    """
    订单结算数据序列化器
    """
    freight = serializers.DecimalField(label='运费', max_digits=10, decimal_places=2)
    skus = CartSKUSerializer(many=True)


class ALLSkuSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = ('id', 'name', 'default_image_url', 'price')


class UncommentsSerializer(serializers.ModelSerializer):
    """序列化输出未评论商品信息"""
    sku = ALLSkuSerializer()

    class Meta:
        model = OrderGoods
        fields = ['comment', 'price', 'score', 'is_anonymous', 'is_commented', 'sku']


class CommentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderGoods
        fields = ['comment', 'score', 'is_anonymous']

    def update(self, instance, validated_data):
        """更新订单商品的评论信息"""
        comment = validated_data['comment']
        score = validated_data['score']
        is_anonymous = validated_data['is_anonymous']

        instance.comment = comment
        instance.score = score
        instance.is_anonymous = is_anonymous

        # 修改是否评论字段
        instance.is_commented = True

        instance.save()

        return instance


class GetCommentsSerializer(serializers.ModelSerializer):
    """获取商品详情页评论信息"""

    username = serializers.CharField(label='用户名')

    class Meta:
        model = OrderGoods
        fields = ['score', 'comment', 'username']
