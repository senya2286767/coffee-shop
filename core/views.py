import json
import io
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
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

    for cart_key, quantity in cart.items():
        # Разделяем ключ на ID товара и стикеры
        parts = cart_key.split('_', 1)
        product_id = parts[0]
        stickers_str = parts[1] if len(parts) > 1 else ""
        stickers_list = stickers_str.split(',') if stickers_str else []

        product = Product.objects.filter(id=product_id).first()
        
        if product:
            item_total = product.price * quantity
            total_price += item_total
            total_quantity += quantity
            
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'total': item_total,
                'stickers': stickers_list,
                'cart_key': cart_key # Передаем уникальный ключ в шаблон
            })

    return render(request, 'core/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_quantity': total_quantity
    })


def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    
    # Получаем стикеры из ссылки (если они есть)
    stickers_str = request.GET.get('stickers', '')
    
    # Создаем уникальный ключ: "1_С собой — тепло" или просто "1", если стикеров нет
    cart_key = f"{product_id}_{stickers_str}" if stickers_str else str(product_id)

    # Добавляем товар в корзину именно по этому ключу
    if cart_key in cart:
        cart[cart_key] += 1
    else:
        cart[cart_key] = 1

    request.session['cart'] = cart
    messages.success(request, f'Товар «{product.name}» добавлен в корзину!')
    return redirect('cart_detail') 


def cart_remove(request, cart_key):
    cart = request.session.get('cart', {})
    if cart_key in cart:
        del cart[cart_key]
        request.session['cart'] = cart
        messages.info(request, 'Товар удален из корзины.')
    return redirect('cart_detail')


def cart_update(request, cart_key):
    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')
        cart = request.session.get('cart', {})
        
        if cart_key in cart:
            if action == 'increase':
                cart[cart_key] += 1
            elif action == 'decrease':
                cart[cart_key] -= 1
                if cart[cart_key] <= 0:
                    del cart[cart_key]
                    
        request.session['cart'] = cart
        request.session.modified = True

        # Пересчитываем итоги
        total_price = 0
        total_quantity = 0
        new_quantity = cart.get(cart_key, 0)
        
        # Получаем ID товара из ключа для ответа JS
        product_id = cart_key.split('_')[0]
        product = get_object_or_404(Product, id=product_id)
        
        for key, qty in cart.items():
            pid = key.split('_')[0]
            p = Product.objects.filter(id=pid).first()
            if p:
                total_price += p.price * qty
                total_quantity += qty

        return JsonResponse({
            'success': True, 
            'new_quantity': new_quantity, 
            'new_total': product.price * new_quantity,
            'cart_total': float(total_price),
            'cart_quantity': total_quantity
        })
    return JsonResponse({'success': False}, status=400)

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'core/product_detail.html', {'product': product})


def sticker_page(request, product_id):
    # Находим товар по ID. Если товара нет — выдаст ошибку 404.
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'core/sticker.html', {'product': product})


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
            # Забираем стикеры из сессии (их туда положил скрипт напарника)
    stickers_list = request.session.get('selected_stickers', [])
    if stickers_list:
        order.stickers = stickers_list
        # Очищаем сессию после того, как перенесли их в заказ
        del request.session['selected_stickers']

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

def save_stickers(request):
    """Сохранение стикеров в сессию (принимает AJAX-запрос от JS)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            stickers = data.get('stickers', [])
            request.session['selected_stickers'] = stickers
            return JsonResponse({'success': True, 'stickers': stickers})
        except json.JSONDecodeError:
            return JsonResponse({'success': False}, status=400)
    return JsonResponse({'success': False}, status=400)

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Ищем пользователя по email (стандартный authenticate ищет по username)
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            return redirect('profile') # <-- Сюда перенаправляем после входа (например, в профиль)
        else:
            messages.error(request, "Неверная почта или пароль")
            
    return render(request, 'core/login.html')


def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Пользователь с такой почтой уже существует")
        else:
            # Создаем нового пользователя. В качестве username используем email.
            user = User.objects.create_user(username=email, email=email, password=password, first_name=first_name)
            login(request, user)
            return redirect('profile') # <-- Сюда перенаправляем после регистрации

    return render(request, 'core/register.html')

@login_required
def profile_view(request):
    # Получаем все заказы текущего пользователя (от новых к старым)
    user_orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'core/profile.html', {
        'orders': user_orders
    })

def logout_view(request):
    logout(request)
    return redirect('catalog')

def save_stickers(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        stickers = data.get('stickers', [])
        product_id = data.get('product_id')
        
        # Сохраняем стикеры в сессию, привязывая их к конкретному товару
        # (формат: {'1': ['С собой', 'Тепло'], '2': ['Кофе']})
        custom_stickers = request.session.get('custom_stickers', {})
        
        if stickers:
            custom_stickers[str(product_id)] = stickers
        elif str(product_id) in custom_stickers:
            # Если стикеры убрали (пустой массив), удаляем их из сессии
            del custom_stickers[str(product_id)]
            
        request.session['custom_stickers'] = custom_stickers
        request.session.modified = True
        
        return JsonResponse({'success': True})
        
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)