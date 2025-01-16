from django.db import models
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager,
                                        PermissionsMixin)
from django_rest_passwordreset.tokens import get_token_generator
from django.contrib.auth.validators import UnicodeUsernameValidator


USER_TYPE = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),
)

STATE_CHOICES = (
    ('cart', 'Статус корзины'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)


# Mодель позволяет использовать email в качестве основного идентификатора
#  пользователя, а также добавлять дополнительные поля, такие как имя или
#  фамилия. Можетно расширить эту модель, добавив другие поля, которые
#  могут быть необходимы для  приложения.


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Поле электронной почты должно быть задано')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, user, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(user, email, password, **extra_fields)


class Users(AbstractBaseUser, PermissionsMixin):
    objects = CustomUserManager()
    USERNAME_FIELD = 'username'
    REQUIRED_FIEDS = ['email']
    email = models.EmailField('E-mail', unique=True)
    company = models.CharField('Компания', max_length=30, blank=True)
    posicion = models.CharField('Должность', max_length=30, blank=True)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField('Пользователь', max_length=150, unique=True)
    first_name = models.CharField('Имя', max_length=30, blank=True)
    last_name = models.CharField('Фамилия', max_length=30, blank=True)
    is_active = models.BooleanField('Активность', default=True)
    is_staff = models.BooleanField('Сотрудник', default=False)
    type = models.CharField('Тип', choices=USER_TYPE, max_length=5,
                            default='buyer')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('username',)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Shop(models.Model):
    objects = models.manager.Manager()
    name = models.CharField(max_length=50, verbose_name='Название')
    url = models.URLField(verbose_name='Ссылка', null=True, blank=True)
    user = models.OneToOneField(Users, verbose_name='Пользователь',
                                blank=True, null=True,
                                on_delete=models.CASCADE)
    state = models.BooleanField(verbose_name='статус получения заказов',
                                default=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = "Список магазинов"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Category(models.Model):
    objects = models.manager.Manager()
    name = models.CharField('Название', max_length=40)
    shops = models.ManyToManyField(Shop, verbose_name='Магазины',
                                   related_name='categories', blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = "Список категорий"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    objects = models.manager.Manager()
    name = models.CharField('Название', max_length=80)
    category = models.ForeignKey(
        Category, verbose_name='Категория', related_name='products',
        blank=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = "Список продуктов"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    objects = models.manager.Manager()
    model = models.CharField('Модель', max_length=80, blank=True)
    external_id = models.PositiveIntegerField('Внешний ИД')
    product = models.ForeignKey(
        Product, verbose_name='Продукт', related_name='product_infos',
        blank=True, on_delete=models.CASCADE)
    shop = models.ForeignKey(
        Shop, verbose_name='Магазин', related_name='product_infos', blank=True,
        on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField('Количество')
    price = models.PositiveIntegerField('Цена')
    price_rrc = models.PositiveIntegerField('Рекомендуемая розничная цена')

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = "Информационный список о продуктах"
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop', 'external_id'],
                                    name='unique_product_info'),
        ]


class Parameter(models.Model):
    objects = models.manager.Manager()
    name = models.CharField('Название', max_length=40)

    class Meta:
        verbose_name = 'Имя параметра'
        verbose_name_plural = "Список имен параметров"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    objects = models.manager.Manager()
    product_info = models.ForeignKey(
        ProductInfo, verbose_name='Информация о продукте',
        related_name='product_parameters', blank=True,
        on_delete=models.CASCADE)
    parameter = models.ForeignKey(
        Parameter, verbose_name='Параметр', related_name='product_parameters',
        blank=True, on_delete=models.CASCADE)
    value = models.CharField('Значение', max_length=100)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'],
                                    name='unique_product_parameter'),
        ]


class Contact(models.Model):
    objects = models.manager.Manager()
    user = models.ForeignKey(
        Users, verbose_name='Пользователь', related_name='contacts',
        blank=True, on_delete=models.CASCADE)
    city = models.CharField('Город', max_length=50)
    street = models.CharField('Улица', max_length=100)
    house = models.CharField('Дом', max_length=15, blank=True)
    structure = models.CharField('Корпус', max_length=10, blank=True)
    building = models.CharField('Строение', max_length=10, blank=True)
    apartment = models.CharField('Квартира', max_length=10, blank=True)
    phone = models.CharField('Телефон', max_length=20)

    class Meta:
        verbose_name = 'Контакты пользователя'
        verbose_name_plural = "Список контактов пользователя"

    def __str__(self):
        return f'{self.city} {self.street} {self.house}'


class Order(models.Model):
    objects = models.manager.Manager()
    user = models.ForeignKey(Users, verbose_name='Пользователь',
                             related_name='orders',
                             blank=True, on_delete=models.CASCADE)
    dt = models.DateTimeField(auto_now_add=True)
    state = models.CharField('Статус', choices=STATE_CHOICES, max_length=15)
    contact = models.ForeignKey(Contact, verbose_name='Контакт', blank=True,
                                null=True,
                                on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Список заказ"
        ordering = ('-dt',)

    def __str__(self):
        return str(self.dt)


class OrderItem(models.Model):
    objects = models.manager.Manager()
    order = models.ForeignKey(
        Order, verbose_name='Заказ', related_name='ordered_items', blank=True,
        on_delete=models.CASCADE)
    product_info = models.ForeignKey(
        ProductInfo, verbose_name='Информация о продукте',
        related_name='ordered_items',
        blank=True, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField('Количество')

    class Meta:
        verbose_name = 'Заказанная позиция'
        verbose_name_plural = "Список заказанных позиций"
        constraints = [
            models.UniqueConstraint(fields=['order_id', 'product_info'],
                                    name='unique_order_item'),
        ]


class ConfirmEmailToken(models.Model):
    class Meta:
        verbose_name = 'Токен подтверждения E-mail'
        verbose_name_plural = 'Токены подтверждения E-mail'

    @staticmethod
    def generate_key():
        """ generates a pseudo random code using os.urandom and binascii.\
            hexlify """
        return get_token_generator().generate_token()
    user = models.ForeignKey(
        Users, related_name='confirm_email_tokens',
        on_delete=models.CASCADE, verbose_name=("Пользователь, который связан \
                                                с паролем сброса токена"))
    created_at = models.DateTimeField('Дата генерации токена',
                                      auto_now_add=True)
    key = models.CharField(("Key"), max_length=64, db_index=True, unique=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ConfirmEmailToken, self).save(*args, **kwargs)

    def __str__(self):
        return "Пароль для сброса токена для пользоавтеля {user}".format(
            user=self.user)
