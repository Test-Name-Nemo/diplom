from django.contrib import admin

from backend.models import (
    Users, Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
    Order, OrderItem, Contact, ConfirmEmailToken)
from django.http import HttpResponseRedirect
from backend.tasks import do_import


class ImportAdmin(admin.ModelAdmin):
    def import_data(self, request, queryset):
        do_import.delay()
        self.message_user(request, "Import task has been started.")
        return HttpResponseRedirect("../")

    import_data.short_description = "Start import task"
    actions = [import_data]

# Удалите существующую регистрацию модели Users
    try:
        admin.site.unregister(Users)
    except admin.sites.NotRegistered:
        pass


@admin.register(Users)
class CustomUserAdmin(ImportAdmin):
    """
    Панель управления пользователями
    """
    model = Users
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password', 'type')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company',
                                      'position')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups',
                       'permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('first_name', 'last_name', 'type',  'email', 'position',
                    'company', 'is_staff', 'is_active')


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'user', 'state']
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    model = Category
    list_display = ['id', 'name']
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'model']
    search_fields = ('name', 'model',)


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    model = ProductInfo
    pass


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ['id']
    search_fields = ('product',)


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'contact']
    search_fields = ('status',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'quantity']
    search_fields = ('order',)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("city", "street", "house", "apartment", "phone",)


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at')
