from django.urls import path
from . import views

urlpatterns = [
    # Главная страница (путь '')
    path('', views.index, name='home'), 
    
    # Каталог (путь 'catalog/')
    path('catalog/', views.catalog, name='catalog'),
    
    # Корзина
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
]