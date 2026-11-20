from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='home'), 
    
    path('catalog/', views.catalog, name='catalog'),
    
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),

    path('product/<int:product_id>/', views.product_detail, name='product_detail'),

    path('sticker/<int:product_id>/', views.sticker_page, name='sticker_page'),
    path('checkout/', views.checkout, name='checkout'),
    path('receipt/<int:order_id>/', views.receipt, name='receipt'),

    path('order/success/<int:order_id>/', views.order_success, name='order_success'),
    path('order/receipt/<int:order_id>/', views.download_receipt, name='download_receipt'),
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<int:post_id>/', views.blog_detail, name='blog_detail'),
    path('stats/', views.stats_page, name='stats_page'),
    path('api/stats/summary/', views.stats_summary, name='api_stats_summary'),
    path('api/stats/popular/', views.stats_popular_products, name='api_stats_popular'),
    path('api/stats/orders/', views.stats_orders_by_day, name='api_stats_orders'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    path('cart/update/', views.cart_update, name='cart_update'), 
    path('cart/remove/<str:cart_key>/', views.cart_remove, name='cart_remove'),
    path('stats/', views.stats_page, name='stats_page'),
    path('admin-stats/', views.admin_stats_view, name='admin_stats'),
    path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)