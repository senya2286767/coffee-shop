from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='home'), 
    
    path('catalog/', views.catalog, name='catalog'),
    
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),

    path('product/<int:product_id>/', views.product_detail, name='product_detail'),

    path('sticker/', views.sticker_page, name='sticker_page'),
        path('checkout/', views.checkout, name='checkout'),
    path('receipt/<int:order_id>/', views.receipt, name='receipt'),
    path('order/success/<int:order_id>/', views.order_success, name='order_success'),
    path('order/receipt/<int:order_id>/', views.download_receipt, name='download_receipt'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)