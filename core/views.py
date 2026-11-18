from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Product, Category, Order, OrderItem
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from xhtml2pdf import pisa

def index(request):
    """Главная страница кофейни (без вывода товаров)"""
    return render(request, 'core/index.html')

def catalog(request):
    """Страница каталога с товарами"""
    products = Product.objects.filter(is_available=True)
    categories = Category.objects.all()
    
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)

    return render(request, 'core/catalog.html', {
        'products': products,
        'categories': categories,
    })

def cart_detail(request):
    """Страница просмотра корзины"""
    cart = request.session.get('cart', {})
    cart_items = []
    total_price = 0

    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=product_id)
        item_total = product.price * quantity
        total_price += item_total
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'total': item_total
        })

    return render(request, 'core/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price
    })

def cart_add(request, product_id):
    """Добавление товара в корзину"""
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})

    if str(product_id) in cart:
        cart[str(product_id)] += 1
    else:
        cart[str(product_id)] = 1

    request.session['cart'] = cart
    messages.success(request, f'Товар «{product.name}» добавлен в корзину!')
    
    return redirect(request.META.get('HTTP_REFERER', 'catalog'))

def cart_remove(request, product_id):
    """Удаление товара из корзины"""
    cart = request.session.get('cart', {})
    if str(product_id) in cart:
        del cart[str(product_id)]
        request.session['cart'] = cart
        messages.info(request, 'Товар удален из корзины.')
    
    return redirect('cart_detail')

def product_detail(request, product_id):
    """Страница конкретного товара"""
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'core/product_detail.html', {'product': product})

def sticker_page(request):
    """Страница кастомизации стакана стикерами"""
    return render(request, 'core/sticker.html')

@login_required
def checkout(request):
    """Оформление заказа из корзины"""
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'Ваша корзина пуста.')
        return redirect('cart_detail')

    order = Order.objects.create(user=request.user)
    total_price = 0

    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=product_id)
        item_price = product.price * quantity
        total_price += item_price
        
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price
        )

    order.total_price = total_price
    order.save()
    request.session['cart'] = {} 

    messages.success(request, 'Заказ успешно оформлен!')
    return redirect('receipt', order_id=order.id)


@login_required
def receipt(request, order_id):
    """Генерация PDF-чека"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    template = get_template('core/receipt_pdf.html')
    html = template.render({'order': order})

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{order.id}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Ошибка при создании PDF', status=500)
        
    return response