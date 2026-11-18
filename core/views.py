import json
import io
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from xhtml2pdf import pisa

from .models import Product, Category, Order, OrderItem, BlogPost
from .forms import RegisterForm


def index(request):
    return render(request, 'core/index.html')


def catalog(request):
    products = Product.objects.filter(is_available=True)
    categories = Category.objects.all()
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)

    return render(request, 'core/catalog.html', {'products': products, 'categories': categories})


def cart_detail(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total_price = 0
    total_quantity = 0

    for product_id, quantity in cart.items():
        product = Product.objects.filter(id=product_id).first()
        if product:
            item_total = product.price * quantity
            total_price += item_total
            total_quantity += quantity
            cart_items.append({'product': product, 'quantity': quantity, 'total': item_total})

    return render(request, 'core/cart.html', {
        'cart_items': cart_items, 'total_price': total_price, 'total_quantity': total_quantity
    })


def cart_add(request, product_id):
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
    cart = request.session.get('cart', {})
    if str(product_id) in cart:
        del cart[str(product_id)]
        request.session['cart'] = cart
        messages.info(request, 'Товар удален из корзины.')
    return redirect('cart_detail')


def cart_update(request, product_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')
        cart = request.session.get('cart', {})
        pid_str = str(product_id)
        
        if pid_str in cart:
            if action == 'increase':
                cart[pid_str] += 1
            elif action == 'decrease':
                cart[pid_str] -= 1
                if cart[pid_str] <= 0:
                    del cart[pid_str]
        elif action == 'increase':
            cart[pid_str] = 1

        request.session['cart'] = cart
        request.session.modified = True

        # Пересчитываем итоги
        total_price = 0
        total_quantity = 0
        new_quantity = cart.get(pid_str, 0)
        product = get_object_or_404(Product, id=product_id)
        
        for pid, qty in cart.items():
            p = Product.objects.filter(id=pid).first()
            if p:
                total_price += p.price * qty
                total_quantity += qty

        return JsonResponse({
            'success': True, 
            'new_quantity': new_quantity, 
            'new_total': product.price * new_quantity,
            'cart_total': total_price,
            'cart_quantity': total_quantity
        })
    return JsonResponse({'success': False}, status=400)


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'core/product_detail.html', {'product': product})


def sticker_page(request):
    return render(request, 'core/sticker.html')


@login_required
def checkout(request):
    """Оформление заказа (принимает и GET, и POST)"""
    cart = request.session.get('cart', {})
    cart_items = []
    total_price = 0
    total_quantity = 0

    # Считаем корзину для отображения на странице оформления
    for product_id, quantity in cart.items():
        product = Product.objects.filter(id=product_id).first()
        if product:
            item_total = product.price * quantity
            total_price += item_total
            total_quantity += quantity
            cart_items.append({'product': product, 'quantity': quantity})

    if not cart_items:
        messages.warning(request, 'Ваша корзина пуста.')
        return redirect('cart_detail')

    if request.method == 'POST':
        # Создаем заказ
        order = Order.objects.create(user=request.user, total_price=total_price)
        
        for item in cart_items:
            OrderItem.objects.create(
                order=order, product=item['product'], quantity=item['quantity'], price=item['product'].price
            )

        # Логика стикеров (принимаем из формы)
        stickers_raw = request.POST.get('stickers_data', '[]')
        try:
            stickers_list = json.loads(stickers_raw)
            if isinstance(stickers_list, list):
                order.stickers = stickers_list
        except json.JSONDecodeError:
            pass

        order.save()
        request.session['cart'] = {}
        request.session.modified = True

        messages.success(request, f'Заказ #{order.id} успешно оформлен!')
        return redirect('receipt', order_id=order.id)

    # Если GET-запрос — показываем страницу checkout.html (вёрстка напарника)
    return render(request, 'core/checkout.html', {
        'cart_items': cart_items, 'total_price': total_price, 'total_quantity': total_quantity
    })


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    pickup_time = order.created_at + timedelta(minutes=15)
    return render(request, 'core/order_success.html', {'order': order, 'pickup_time': pickup_time})


@login_required
def receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    template = get_template('core/receipt_pdf.html')
    html = template.render({'order': order})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{order.id}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Ошибка при создании PDF', status=500)
    return response


@login_required
def download_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    template_path = 'core/receipt_pdf.html'
    context = {'order': order}
    response = io.BytesIO()
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Ошибка при генерации PDF', status=500)
    response.seek(0)
    return FileResponse(response, as_attachment=True, filename=f'receipt_{order.id}.pdf')


def blog_list(request):
    posts = BlogPost.objects.all().order_by('-created_at')
    return render(request, 'core/blog_list.html', {'posts': posts})


def blog_detail(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    return render(request, 'core/blog_detail.html', {'post': post})


@staff_member_required
def stats_page(request):
    return render(request, 'core/stats.html')


@staff_member_required
def stats_summary(request):
    total_revenue = Order.objects.aggregate(Sum('total_price'))['total_price__sum'] or 0
    return JsonResponse({'total_revenue': float(total_revenue), 'total_orders': Order.objects.count()})


@staff_member_required
def stats_popular_products(request):
    data = (OrderItem.objects.values('product__name').annotate(count=Count('id')).order_by('-count')[:5])
    return JsonResponse(list(data), safe=False)


@staff_member_required
def stats_orders_by_day(request):
    data = (Order.objects.annotate(date=TruncDate('created_at')).values('date').annotate(count=Count('id')).order_by('date'))
    result = [{'date': item['date'].strftime('%d.%m.%Y'), 'count': item['count']} for item in data]
    return JsonResponse(result, safe=False)


def register(request):
    if request.user.is_authenticated:
        return redirect('catalog')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('catalog')
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})