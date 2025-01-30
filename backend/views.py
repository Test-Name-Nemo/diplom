from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from django.http import JsonResponse
from rest_framework.response import Response
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from requests import get
from ujson import loads as load_json
from yaml import load as load_yaml, Loader
from backend.models import Shop, Category, Product, ProductInfo, Parameter, \
    ProductParameter, Order, OrderItem, Contact, ConfirmEmailToken
from backend.serializers import UserSerializer, CategorySerializer, \
    ShopSerializer, ProductInfoSerializer, OrderItemSerializer, \
    OrderSerializer, ContactSerializer
from backend.signals import new_user_registered, new_order
from rest_framework.permissions import IsAuthenticated


class RegisterAccount(APIView):

    """Класс для регистрации покупателя"""
    throttle_scope = 'register'

    def post(self, request, *args, **kwargs):
        if {'first_name', 'last_name', 'email', 'password', 'company',
            'position'}.issubset(request.data):
            # Проверяем наличие дубликатов email
            try:
                validate_password(request.data['password'])
            except Exception as error:
                return Response({'status': False, 'error': {'password': error}})
            else:
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    token, _ = ConfirmEmailToken.objects.get_or_create(
                        user_id=user.id)
                    return Response(
                        {'status': True,
                         'Токен для подтверждения e-mail': token.key})
                else:
                    return Response({'status': False,
                                    'error': user_serializer.errors})

        return Response({'status': False, 'error': 'Не указаны все поля'})


class ConfirmAccount(APIView):

    """Класс для подтверждения регистрации""" 
    def post(self, request, *args, **kwargs):
        if all(key in request.data for key in ['email', 'token']):
            token = ConfirmEmailToken.objects.filter(
                user__email=request.data['email'],
                key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return Response({
                    'Status': True
                })
            else:
                return Response({'Status': False,
                                 'Errors': 'Неправильно указан token\
                                    или email'})
        return Response({'Status': False,
                         'Errors': 'Не указыны все аргументы'})


class LoginAccount(APIView):

    # Класс для авторизации пользователей методом POST
    def post(self, request, *args, **kwargs):
        if all(key in request.data for key in ['email', 'password']):
            user = authenticate(request, username=request.data['email'],
                                password=request.data['password'])
            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return Response({'status': True, 'token': token.key})
            return Response({'status': False, 'error': 'Ошибка входа'})
        return Response({'status': False, 'error': 'Не указаны все поля'})


class AccountDetails(APIView):
    # Класс для работы данными пользователя
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Редактирование методом POST
    def post(self, request, *args, **kwargs):
        '''проверка на обязательные аргументы'''
        if 'password' in request.data:
            # проверка пароля на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {
                    'password': error_array}})
            else:
                request.user.set_password(request.data['password'])

        # проверка остальных данных
        user_serializer = UserSerializer(request.user, data=request.data,
                                         partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False,
                                 'Errors': user_serializer.errors})


class CategoryView(ListAPIView):

    # Класс для просмотра категорий товара
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):

    # Класс для просмотра списка магазинов
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class PartnerUpdate(APIView):
    '''Класс для обновления прайса от поставщика '''
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для \
                                 магазинов'}, status=403)
        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})
            else:
                stream = get(url).content

                data = load_yaml(stream, Loader=Loader)

                shop, _ = Shop.objects.get_or_create(name=data['shop'],
                                                     user_id=request.user.id)
                for category in data['categories']:
                    category_object, _ = Category.objects.get_or_create(
                        id=category['id'], name=category['name'])
                    category_object.shops.add(shop.id)
                    category_object.save()
                ProductInfo.objects.filter(shop_id=shop.id).delete()
                for item in data['goods']:
                    product, _ = Product.objects.get_or_create(
                        name=item['name'], category_id=item['category'])
                    product_info = ProductInfo.objects.create(
                        product_id=product.id,
                        external_id=item['id'],
                        model=item['model'],
                        price=item['price'],
                        price_rrc=item['price_rrc'],
                        quantity=item['quantity'],
                        shop_id=shop.id)
                    for name, value in item['parameters'].items():
                        parameter_object, _ = Parameter.objects.get_or_create(
                            name=name)
                        ProductParameter.objects.create(
                            product_info_id=product_info.id,
                            parameter_id=parameter_object.id,
                            value=value)

                return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})


class ProductInfoView(APIView):
    ''' Класс для поиска товаров'''
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')
        if shop_id:
            query = query & Q(shop_id=shop_id)
        if category_id:
            query = query & Q(product__category_id=category_id)
        # фильтруем и отбрасываем дуликаты
        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()
        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class BasketView(APIView):
    ''' Класс для работы с корзиной покупателей'''
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
            ).annotate(total_sum=Sum(F('ordered_items__quantity') * F(
                'ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    '''редактировать корзину'''
    def post(self, request, *args, **kwargs):
        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный \
                                     формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state='basket')
                objects_created = 0
                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors':
                                                 str(error)})
                        else:
                            objects_created += 1
                    else:
                        return JsonResponse({'Status': False, 'Errors':
                                             serializer.errors})
                return JsonResponse({'Status': True, 'Создано объектов':
                                     objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})

    ''' удалить товары из корзины'''
    def delete(self, request, *args, **kwargs):
        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id,
                                                    state='basket')
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов':
                                     deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})

    '''добавить позиции товара в корзину'''
    def put(self, request, *args, **kwargs):
        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный \
                                     формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state='basket')
                objects_updated = 0
                for order_item in items_dict:
                    if isinstance(order_item['id'], int) and \
                            isinstance(order_item['quantity'], int):
                        objects_updated += OrderItem.objects.filter(
                            order_id=basket.id, id=order_item['id']).update(
                            quantity=order_item['quantity'])

                return JsonResponse({'Status': True, 'Обновлено объектов':
                                     objects_updated})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})


class PartnerState(APIView):
    ''' Класс для работы со статусом'''
    permission_classes = [IsAuthenticated]

    # получить текущий статус
    def get(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для \
                                 магазинов'}, status=403)
        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # изменить текущий статус
    def post(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для \
                                 магазинов'}, status=403)
        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(
                    state=bool(state))
                return JsonResponse({'Status': True})
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})


class PartnerOrders(APIView):
    '''Класс для получения заказов поставщиками'''
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для \
                                 магазинов'}, status=403)
        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id)\
            .exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter')\
            .select_related('contact').annotate(total_sum=Sum(F(
                'ordered_items__quantity') * F(
                    'ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    'Класс для работы с контактами покупателей'
    permission_classes = [IsAuthenticated]

    'Получить контакты'
    def get(self, request, *args, **kwargs):
        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    'добавить новый контакт'
    def post(self, request, *args, **kwargs):
        # Проверяем наличие необходимых данных
        if all(key in request.data for key in ['city', 'street', 'phone']):
            # Создаем новый словарь для данных
            data = request.data.copy()  # Создадим копию request.data
            data.update({'user': request.user.id})  # Добавляем идентификатор пользователя
            serializer = ContactSerializer(data=data)  # Передаем данные сериализатору
            # Проверяем валидность данных
            if serializer.is_valid():
                try:
                    serializer.save()  # Сохраняем данные
                    return JsonResponse({'Status': True}, status=201)  # Создание успешно завершено
                except Exception as e:
                    return JsonResponse({'Status': False, 'Errors': 'Ошибка при сохранении данных: {}'.format(str(e))}, status=500)
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

    'удалить контакт'
    def delete(self, request, *args, **kwargs):
        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов':
                                     deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})

    'редактировать контакт'
    def put(self, request, *args, **kwargs):
        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(
                    id=request.data['id'], user_id=request.user.id).first()
                print(contact)
                if contact:
                    serializer = ContactSerializer(contact, data=request.data,
                                                   partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True})
                    else:
                        return JsonResponse({'Status': False, 'Errors':
                                             serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})


class OrderView(APIView):
    '''Класс, получения заказов пользователями'''
    permission_classes = [IsAuthenticated]
    '''Получение списка  заказанных товаров'''
    def get(self, request, *args, **kwargs):
        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter')\
            .select_related('contact').annotate(total_sum=Sum(F(
                'ordered_items__quantity') * F(
                    'ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    '''Функция подтверждения заказа'''
    def post(self, request, *args, **kwargs):
        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit():
                try:
                    is_updated = Order.objects.filter(
                        user_id=request.user.id, id=request.data['id']).update(
                        contact_id=request.data['contact'],
                        state='new')
                except IntegrityError as error:
                    print(error)
                    return JsonResponse({'Status': False, 'Errors':
                                         'Неправильно указаны аргументы'})
                else:
                    if is_updated:
                        new_order.send(sender=self.__class__,
                                       user_id=request.user.id)
                        return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все \
                             необходимые аргументы'})
