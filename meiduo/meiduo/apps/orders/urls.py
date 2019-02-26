from django.conf.urls import url

from . import views

urlpatterns = [
    # 去结算
    url(r'^orders/settlement/$', views.OrderSettlementView.as_view()),
    # 保存订单
    url(r'^orders/$', views.CommitOrderView.as_view()),
    # 去评论,展示未评论商品
    url(r'^orders/(?P<pk>\d+)/uncommentgoods/$', views.UncommentsView.as_view()),
    # 评论保存
    url(r'^orders/(?P<pk>\d+)/comments/$', views.UncommentsView.as_view()),
    # 获取商品详情页评论信息
    url(r'^skus/(?P<pk>\d+)/comments/$', views.GetCommentsView.as_view()),
]
