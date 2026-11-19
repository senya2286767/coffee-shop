import json
import io
from datetime import timedelta
from django.utils import timezone
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
from xhtml2pdf import pisa
from django.contrib.staticfiles import finders

from .models import Product, Category, Order, OrderItem, BlogPost
from .forms import RegisterForm
from django.conf import settings
from django.shortcuts import get_object_or_404


def index(request):
    return render(request, 'core/index.html')


def catalog(request):
    categories = Category.objects.all()
    products = Product.objects.all()
    
    selected_categories = request.GET.getlist('category')
    
    if selected_categories:
        products = products.filter(category__slug__in=selected_categories)

    context = {
        'categories': categories,
        'products': products,
        'selected_categories': selected_categories, 
    }
    return render(request, 'core/catalog.html', context)


def cart_detail(request):
    cart = request.session.get('cart', {})
    custom_stickers = request.session.get('custom_stickers', {})
    cart_items = []
    total_price = 0
    total_quantity = 0

    for cart_key, quantity in cart.items():
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
                'cart_key': cart_key
            })

    return render(request, 'core/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_quantity': total_quantity
    })


def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    
    stickers_str = request.GET.get('stickers', '')
    
    cart_key = f"{product_id}_{stickers_str}" if stickers_str else str(product_id)

    if cart_key in cart:
        cart[cart_key] += 1
    else:
        cart[cart_key] = 1

    request.session['cart'] = cart
    messages.success(request, f'Товар «{product.name}» добавлен в корзину!')
    return redirect('cart_detail') 


def cart_remove(request, cart_key):
    """Удаление конкретного товара (со стикерами или без) из корзины"""
    cart = request.session.get('cart', {})
    
    # Если такой ключ есть в корзине — удаляем его
    if cart_key in cart:
        del cart[cart_key]
        request.session['cart'] = cart
        request.session.modified = True # Обязательно говорим Django, что сессия изменилась
        messages.info(request, 'Товар удален из корзины.')
        
    return redirect('cart_detail')


def cart_update(request, product_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')
        cart = request.session.get('cart', {})
        
        # Ищем ключ (с ID товара или с ID товара + стикеры)
        cart_key = next((key for key in cart.keys() if key.startswith(str(product_id))), None)
        
        if cart_key:
            if action == 'increase':
                cart[cart_key] += 1
            elif action == 'decrease':
                cart[cart_key] -= 1
                if cart[cart_key] <= 0:
                    del cart[cart_key]
                    
        request.session['cart'] = cart
        request.session.modified = True 

        # Пересчитываем итоги для ответа
        total_price = 0
        total_quantity = 0
        new_quantity = cart.get(cart_key, 0) if cart_key else 0
        product = get_object_or_404(Product, id=product_id)
        
        for pid_key, qty in cart.items():
            # Достаем ID товара из ключа (до подчеркивания)
            pid = pid_key.split('_')[0]
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


def sticker_page(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'core/sticker.html', {'product': product})


@login_required
def checkout(request):
    """Страница оформления заказа"""
    cart = request.session.get('cart', {})
    
    cart_items = []
    total_price = 0
    total_quantity = 0
    all_stickers = {}

    for cart_key, quantity in cart.items():
        parts = cart_key.split('_', 1)
        product_id = parts[0]
        stickers_str = parts[1] if len(parts) > 1 else ""

        product = Product.objects.filter(id=product_id).first()
        
        if product:
            item_total = product.price * quantity
            total_price += item_total
            total_quantity += quantity
            
            cart_items.append({
                'product': product, 
                'quantity': quantity
            })
            
            if stickers_str:
                all_stickers[str(product.id)] = stickers_str.split(',')

    if not cart_items:
        messages.error(request, "Ваша корзина пуста")
        return redirect('cart_detail')

    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        order = Order.objects.create(
            user=request.user,
            total_price=total_price,
            status='new',
            stickers=all_stickers 
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                price=item['product'].price
            )

        request.session['cart'] = {}
        request.session['custom_stickers'] = {}
        request.session.modified = True

        return redirect('order_success', order_id=order.id)

    return render(request, 'core/checkout.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_quantity': total_quantity
    })

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    pickup_time = order.created_at + timedelta(minutes=15)
    return render(request, 'core/order_success.html', {'order': order, 'pickup_time': pickup_time})


def link_callback(uri, rel):
    """Переводит URL статики в абсолютный путь на диске без ошибок безопасности"""
    sUrl = settings.STATIC_URL      # '/static/'
    sRoot = settings.STATIC_ROOT    # Папка со статикой
    
    if not sRoot:
        sRoot = os.path.join(settings.BASE_DIR, 'static')

    if uri.startswith(sUrl):
        path = os.path.join(sRoot, uri.replace(sUrl, ""))
        if os.path.isfile(path):
            return path
    return uri


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
    user_orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'orders': user_orders
    }

    # Если зашел администратор, считаем для него статистику
    if request.user.is_staff:
        today = timezone.now().date()
        
        orders_today = Order.objects.filter(created_at__date=today)
        revenue_today = orders_today.aggregate(total=Sum('total_price'))['total'] or 0
        count_today = orders_today.count()
        avg_check = int(revenue_today / count_today) if count_today > 0 else 0
        in_progress = Order.objects.filter(status__in=['new', 'processing']).count()

        chart_labels = []
        chart_data = []
        weekdays = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            daily_revenue = Order.objects.filter(created_at__date=day).aggregate(total=Sum('total_price'))['total'] or 0
            label = f"{day.day} {weekdays[day.weekday()]}"
            chart_labels.append(label)
            chart_data.append(float(daily_revenue))

        recent_orders = Order.objects.all().order_by('-created_at')[:5]

        context.update({
            'today_date': today,
            'revenue_today': revenue_today,
            'count_today': count_today,
            'avg_check': avg_check,
            'in_progress': in_progress,
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            'recent_orders': recent_orders,
        })

    return render(request, 'core/profile.html', context)

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
            return redirect('profile')
        else:
            messages.error(request, "Неверная почта или пароль")
            
    return render(request, 'core/login.html')

@staff_member_required # Доступ только для админов
def admin_stats_view(request):
    today = timezone.now().date()
    
    # 1. Статистика за сегодня
    orders_today = Order.objects.filter(created_at__date=today)
    revenue_today = orders_today.aggregate(total=Sum('total_price'))['total'] or 0
    count_today = orders_today.count()
    avg_check = int(revenue_today / count_today) if count_today > 0 else 0
    
    # "В работе" (заказы со статусом new или processing)
    in_progress = Order.objects.filter(status__in=['new', 'processing']).count()

    # 2. Данные для графика (за последние 7 дней)
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1): # От 6 дней назад до сегодня
        day = today - timedelta(days=i)
        daily_revenue = Order.objects.filter(created_at__date=day).aggregate(total=Sum('total_price'))['total'] or 0
        
        # Форматируем дату для графика (например, "11 ср")
        months = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
        weekdays = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        label = f"{day.day} {weekdays[day.weekday()]}"
        
        chart_labels.append(label)
        chart_data.append(float(daily_revenue))

    # 3. Последние 5 заказов для таблицы
    recent_orders = Order.objects.all().order_by('-created_at')[:5]

    context = {
        'today_date': today,
        'revenue_today': revenue_today,
        'count_today': count_today,
        'avg_check': avg_check,
        'in_progress': in_progress,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'recent_orders': recent_orders,
        'admin_name': request.user.first_name or request.user.username
    }
    return render(request, 'core/admin_stats.html', context)

def logout_view(request):
    logout(request)
    return redirect('catalog')