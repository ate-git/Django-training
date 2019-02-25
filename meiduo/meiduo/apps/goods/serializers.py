from drf_haystack.serializers import HaystackSerializerfrom rest_framework import serializersfrom .models import SKUfrom .search_indexes import SKUIndexclass SKUSerializer(serializers.ModelSerializer):    """商品列表界面"""    class Meta:        model = SKU        fields = ['id', 'name', 'price', 'default_image_url', 'comments']class SKUSearchSerializer(HaystackSerializer):    """    SKU索引结果数据序列化器    """    object = SKUSerializer(read_only=True)    class Meta:        index_classes = [SKUIndex]        fields = ('text', 'object')class OrderGoodsSerialize(serializers.ModelSerializer):    sku = SKUSerializer()    class Meta:        model = OrderGoods        fields = ['sku','count','price']class OrderListSerializer(serializers.ModelSerializer):    skus = OrderGoodsSerialize(many=True)    create_time = serializers.DateTimeField(label='保存日期', format='%Y-%m-%d %H:%M:%S')    class Meta:        model = OrderInfo        fields = ['order_id','create_time','skus','total_amount','pay_method','status']