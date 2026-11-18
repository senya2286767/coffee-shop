from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Product, Category, Order, OrderItem, BlogPost
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from xhtml2pdf import pisa
<<<<<<< HEAD
import json
=======
from django.http import JsonResponse
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from .forms import RegisterForm
>>>>>>> 57ae933e555b02c47b807d81eeba63759c1ab5bf

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
    total_quantity = 0  # <--- 1. ДОБАВЛЯЕМ ПЕРЕМЕННУЮ

    for product_id, quantity in cart.items():
        # Небольшой лайфхак: лучше использовать filter().first(), 
        # чтобы страница не падала с ошибкой 404, если товар удалили из базы, а он остался в корзине.
        product = Product.objects.filter(id=product_id).first()
        
        if product: # Проверяем, что товар существует
            item_total = product.price * quantity
            total_price += item_total
            total_quantity += quantity # <--- 2. СЧИТАЕМ ОБЩЕЕ КОЛИЧЕСТВО
            
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'total': item_total
            })

    return render(request, 'core/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_quantity': total_quantity  # <--- 3. ПЕРЕДАЕМ В ШАБЛОН
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

def cart_update(request, product_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')

        # 1. Получаем текущую корзину из сессии (или создаем пустую)
        cart = request.session.get('cart', {})
        
        # ID товара в сессии всегда хранится как строка
        product_id_str = str(product_id)

        # 2. Меняем количество
        if product_id_str in cart:
            if action == 'increase':
                cart[product_id_str]['quantity'] += 1
            elif action == 'decrease':
                cart[product_id_str]['quantity'] -= 1
                # Если количество стало 0, удаляем товар из корзины
                if cart[product_id_str]['quantity'] <= 0:
                    del cart[product_id_str]
        else:
            # Если товара еще нет в корзине, а нажали "+"
            if action == 'increase':
                product = get_object_or_404(Product, id=product_id)
                cart[product_id_str] = {
                    'quantity': 1,
                    'price': str(product.price) # Сохраняем цену как строку для JSON
                }

        # 3. Сохраняем обновленную корзину обратно в сессию
        request.session['cart'] = cart
        request.session.modified = True # Сообщаем Django, что сессия изменилась

        # 4. Пересчитываем общую сумму и количество
        total_quantity = 0
        total_price = 0
        new_quantity = 0
        new_total = 0

        for pid, item_data in cart.items():
            qty = item_data['quantity']
            price = float(item_data['price'])
            
            total_quantity += qty
            total_price += qty * price
            
            # Если это тот товар, который мы только что изменили
            if pid == product_id_str:
                new_quantity = qty
                new_total = qty * price

        # 5. Возвращаем ответ для JS
        return JsonResponse({
            'success': True,
            'new_quantity': new_quantity,
            'new_total': new_total,
            'cart_total': total_price,
            'cart_quantity': total_quantity
        })
        
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

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



@login_required # Заказ могут оформлять только авторизованные пользователи
def checkout(request):
    """Страница оформления заказа"""
    cart = request.session.get('cart', {})
    
    # Считаем итоги для правой колонки
    cart_items = []
    total_price = 0
    total_quantity = 0

    for product_id, quantity in cart.items():
        product = Product.objects.filter(id=product_id).first()
        if product:
            item_total = product.price * quantity
            total_price += item_total
            total_quantity += quantity
            cart_items.append({'product': product, 'quantity': quantity})

    if not cart_items:
        messages.error(request, "Ваша корзина пуста")
        return redirect('cart_detail')

    if request.method == 'POST':
        # 1. Получаем данные из формы
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        delivery = request.POST.get('delivery')
        payment = request.POST.get('payment')

        # 2. Создаем Заказ (Order)
        order = Order.objects.create(
            user=request.user,
            total_price=total_price,
            status='new' # Или 'processing', в зависимости от вашей логики
        )

        # 3. Создаем позиции заказа (OrderItem)
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                price=item['product'].price
            )

        # 4. Очищаем корзину
        request.session['cart'] = {}
        request.session.modified = True

        # 5. Перенаправляем на страницу успеха или на PDF-чек
        # Если у вас есть страница с чеком (PDF), укажите её URL:
        # return redirect('receipt_pdf', order_id=order.id)
        
        # Пока просто перенаправим на главную или в профиль
        messages.success(request, f"Заказ #{order.id} успешно оформлен!")
        return redirect('catalog') # Замените на нужный URL

    # Если это GET-запрос, просто показываем форму
    return render(request, 'core/checkout.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_quantity': total_quantity
    })

def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Рассчитываем время готовности (например, + 15 минут от времени создания заказа)
    pickup_time = order.created_at + timedelta(minutes=15)
    
    return render(request, 'core/order_success.html', {
        'order': order,
        'pickup_time': pickup_time
    })

def download_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    template_path = 'core/receipt_pdf.html' # Путь к вашему html-шаблону чека
    context = {'order': order}
    
    response = io.BytesIO()
    template = get_template(template_path)
    html = template.render(context)
    
    # Создаем PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Ошибка при генерации PDF', status=500)
        
    response.seek(0)
    return FileResponse(response, as_attachment=True, filename=f'receipt_{order.id}.pdf')

def blog_list(request):
    """Страница со списком всех статей"""
    posts = BlogPost.objects.all().order_by('-created_at')
    return render(request, 'core/blog_list.html', {'posts': posts})


def blog_detail(request, post_id):
    """Страница одной статьи"""
    post = get_object_or_404(BlogPost, id=post_id)
    return render(request, 'core/blog_detail.html', {'post': post})

@staff_member_required
def stats_page(request):
    return render(request, 'core/stats.html')

@staff_member_required
def stats_summary(request):
    total_revenue = Order.objects.aggregate(Sum('total_price'))['total_price__sum'] or 0
    total_orders = Order.objects.count()
    return JsonResponse({'total_revenue': float(total_revenue), 'total_orders': total_orders})

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
    """Страница регистрации нового пользователя"""
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
