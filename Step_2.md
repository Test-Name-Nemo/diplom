# Этап 2. Проработка моделей данных

## Критерии достижения:

Создание моделей и дополнительных методов.

## Порядок выполнения
Данная структура может быть изменена под конретные цели вашего дипломного проекта.

### Создать модели:
    1. Shop
        - name 
        - url
        - user (o2o -> CustomUser)
        - state
    2. Category
        - name
        - shops (m2m -> Shop)
    3. Product
        - name
        - category (Fk -> Category) 
    4. ProductInfo
        - model  
        - exteral_id
        - product (Fk -> Product)
        - shop (Fk -> Shop)
        - quantity
        - price
        - price_rrc
    5. Parameter
        - name
    6. ProductParameter
        - product_info (Fk -> ProductInfo)
        - parameter (Fk -> Parameter)
        - value
    9. Contact
        - user (Fk -> Customuser)
        - city
        - street
        - hause
        - structure
        - building
        - apartment
        - phone
    7. Order
        - user (Fk -> Customuser)
        - dt
        - state
        - contact (Fk -> Contact)
    8. OrderItem
        - order (Fk -> Orrder)
        - product_info (Fk -> ProductInfo)
        - quantity