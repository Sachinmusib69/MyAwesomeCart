from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from .models import Product, Contact, Orders, OrderUpdate
from math import ceil
import json
import hashlib
import hmac
import uuid
import razorpay
from razorpay.errors import BadRequestError, GatewayError, ServerError


def _cart_details(items):
    if not isinstance(items, dict) or not items:
        raise ValueError('Your cart is empty.')

    quantities = {}
    for cart_product_id, item in items.items():
        try:
            raw_id = cart_product_id[2:] if cart_product_id.startswith('pr') else cart_product_id
            product_id = int(raw_id)
            quantity = int(item[0])
        except (TypeError, ValueError, IndexError, AttributeError) as exc:
            raise ValueError('Your cart contains an invalid item.') from exc
        if quantity < 1 or quantity > 99:
            raise ValueError('Cart quantities must be between 1 and 99.')
        quantities[product_id] = quantities.get(product_id, 0) + quantity

    products = Product.objects.in_bulk(quantities)
    if len(products) != len(quantities):
        raise ValueError('A product in your cart is no longer available.')

    clean_items = {}
    total_rupees = 0
    for product_id, quantity in quantities.items():
        product = products[product_id]
        total_rupees += product.price * quantity
        clean_items['pr%s' % product_id] = [quantity, product.product_name, product.price]
    return total_rupees, clean_items

def index(request):
    allProds = []
    catprods = Product.objects.values('category', 'id')
    cats = {item['category'] for item in catprods}
    for cat in cats:
        prod = Product.objects.filter(category=cat)
        n = len(prod)
        nSlides = n // 4 + ceil((n / 4) - (n // 4))
        allProds.append([prod, range(1, nSlides), nSlides])
    params = {'allProds':allProds}
    return render(request, 'shop/index.html', params)


def about(request):
    return render(request, 'shop/about.html')


def contact(request):
    thank = False
    if request.method=="POST":
        name = request.POST.get('name', '')
        email = request.POST.get('email', '')
        phone = request.POST.get('phone', '')
        desc = request.POST.get('desc', '')
        contact = Contact(name=name, email=email, phone=phone, desc=desc)
        contact.save()
        thank = True
    return render(request, 'shop/contact.html', {'thank': thank})


def tracker(request):
    if request.method=="POST":
        orderId = request.POST.get('orderId', '')
        email = request.POST.get('email', '')
        try:
            order = Orders.objects.filter(order_id=orderId, email=email)
            if len(order)>0:
                update = OrderUpdate.objects.filter(order_id=orderId)
                updates = []
                for item in update:
                    updates.append({'text': item.update_desc, 'time': item.timestamp})
                    response = json.dumps({"status":"success", "updates": updates, "itemsJson": order[0].items_json}, default=str)
                return HttpResponse(response)
            else:
                return HttpResponse('{"status":"noitem"}')
        except Exception as e:
            return HttpResponse('{"status":"error"}')

    return render(request, 'shop/tracker.html')


def searchMatch(query, item):
    '''return true only if query matches the item'''
    if query in item.desc.lower() or query in item.product_name.lower() or query in item.category.lower():
        return True
    else:
        return False

def search(request):
    query = request.GET.get('search', '').strip()
    allProds = []
    catprods = Product.objects.values('category', 'id')
    cats = {item['category'] for item in catprods}
    for cat in cats:
        prodtemp = Product.objects.filter(category=cat)
        prod = [item for item in prodtemp if searchMatch(query, item)]

        n = len(prod)
        nSlides = n // 4 + ceil((n / 4) - (n // 4))
        if len(prod) != 0:
            allProds.append([prod, range(1, nSlides), nSlides])
    params = {'allProds': allProds, "msg": ""}
    if len(allProds) == 0 or len(query)<4:
        params = {'msg': "Please make sure to enter relevant search query"}
    return render(request, 'shop/search.html', params)


def productView(request, myid):

    # Fetch the product using the id
    product = Product.objects.filter(id=myid)
    return render(request, 'shop/prodView.html', {'product':product[0]})


def checkout(request):
    return render(request, 'shop/checkout.html')


@require_POST
def create_razorpay_order(request):
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return JsonResponse({'error': 'Razorpay credentials are not configured.'}, status=500)

    try:
        payload = json.loads(request.body or '{}')
        if not isinstance(payload, dict):
            raise ValueError('Invalid request body.')
        customer = payload.get('customer') or {}
        if not isinstance(customer, dict):
            raise ValueError('Customer details are invalid.')
        total_rupees, clean_items = _cart_details(payload.get('items'))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc) or 'Invalid request.'}, status=400)

    amount_paise = total_rupees * 100
    if amount_paise < 100:
        return JsonResponse({'error': 'The minimum payment amount is Rs. 1.00.'}, status=400)

    receipt = uuid.uuid4().hex
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        razorpay_order = client.order.create(data={
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': receipt,
        })
    except BadRequestError as exc:
        if 'auth' in str(exc).lower() or 'api key' in str(exc).lower():
            return JsonResponse({'error': 'Razorpay authentication failed. Check the test API keys.'}, status=401)
        return JsonResponse({'error': 'Razorpay could not create the order.'}, status=500)
    except (GatewayError, ServerError):
        return JsonResponse({'error': 'Razorpay could not create the order. Please try again.'}, status=500)
    except Exception:
        return JsonResponse({'error': 'Razorpay order creation failed.'}, status=500)

    order_id = str(razorpay_order.get('id', ''))
    if not order_id:
        return JsonResponse({'error': 'Razorpay returned an invalid order.'}, status=500)
    if (int(razorpay_order.get('amount', -1)) != amount_paise or
            razorpay_order.get('currency') != 'INR'):
        return JsonResponse({'error': 'Razorpay returned order details that do not match the cart.'}, status=500)

    try:
        order = Orders.objects.create(
            items_json=json.dumps(clean_items),
            name=str(customer.get('name', ''))[:90],
            email=str(customer.get('email', ''))[:111],
            address=(str(customer.get('address1', '')) + ' ' + str(customer.get('address2', '')))[:111],
            city=str(customer.get('city', ''))[:111],
            state=str(customer.get('state', ''))[:111],
            zip_code=str(customer.get('zip_code', ''))[:111],
            phone=str(customer.get('phone', ''))[:111],
            amount=total_rupees,
        )
        OrderUpdate.objects.create(
            order_id=order.order_id,
            update_desc='Order created; awaiting Razorpay payment',
        )
    except Exception:
        return JsonResponse({'error': 'Order could not be saved. Please try again.'}, status=500)

    order_map = request.session.get('razorpay_order_map', {})
    order_map[order_id] = order.order_id
    while len(order_map) > 20:
        order_map.pop(next(iter(order_map)))
    request.session['razorpay_order_map'] = order_map

    return JsonResponse({
        'order_id': order_id,
        'amount': int(razorpay_order.get('amount', amount_paise)),
        'currency': razorpay_order.get('currency', 'INR'),
        'key_id': settings.RAZORPAY_KEY_ID,
    })


@require_POST
def verify_razorpay_payment(request):
    if not settings.RAZORPAY_KEY_SECRET:
        return JsonResponse({'error': 'Razorpay credentials are not configured.'}, status=500)
    try:
        payload = json.loads(request.body or '{}')
        if not isinstance(payload, dict):
            raise ValueError('Invalid request body.')
    except (TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid request body.'}, status=400)

    payment_id = payload.get('razorpay_payment_id')
    order_id = payload.get('razorpay_order_id')
    signature = payload.get('razorpay_signature')
    if not all(isinstance(value, str) and value for value in (payment_id, order_id, signature)):
        return JsonResponse({'error': 'Payment ID, order ID, and signature are required.'}, status=400)

    order_map = request.session.get('razorpay_order_map', {})
    local_order_id = order_map.get(order_id)
    if not local_order_id:
        return JsonResponse({'error': 'This payment order is not associated with your session.'}, status=400)

    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode('utf-8'),
        ('%s|%s' % (order_id, payment_id)).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        return JsonResponse({'error': 'Payment signature verification failed.'}, status=400)

    order = Orders.objects.filter(order_id=local_order_id).first()
    if order is None:
        return JsonResponse({'error': 'The related order could not be found.'}, status=400)

    if not OrderUpdate.objects.filter(
        order_id=order.order_id, update_desc='Payment verified by Razorpay'
    ).exists():
        OrderUpdate.objects.create(
            order_id=order.order_id,
            update_desc='Payment verified by Razorpay',
        )
    order_map.pop(order_id, None)
    request.session['razorpay_order_map'] = order_map
    return JsonResponse({'success': True, 'message': 'Payment verified successfully.'})
