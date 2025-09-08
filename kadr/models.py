from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
import re


class User(models.Model): # стандартная модель пользователей
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    age = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


from django.db import models
from django.contrib.auth.models import User

class Pharmacy(models.Model):
    name = models.CharField('Название аптеки', max_length=100)
    address = models.CharField('Адрес', max_length=200)
    phone = models.CharField('Телефон', max_length=15, blank=True)
    is_main = models.BooleanField('Главная аптека', default=False,
                                 help_text='Отметьте, если это главная аптека')
    main_pharmacy = models.ForeignKey('self', on_delete=models.SET_NULL,
                                     null=True, blank=True, 
                                     verbose_name='Подчиняется аптеке',
                                     limit_choices_to={'is_main': True},
                                     help_text='Выберите главную аптеку, если эта аптека является филиалом')
    
    class Meta:
        verbose_name = 'Аптека'
        verbose_name_plural = 'Аптеки'
    
    def __str__(self):
        main_status = " (Главная)" if self.is_main else ""
        return f"{self.name}{main_status} - {self.address}"
    
    def clean(self):
        """Валидация данных"""
        from django.core.exceptions import ValidationError
        
        # Нельзя чтобы аптека была главной и одновременно подчинялась другой
        if self.is_main and self.main_pharmacy:
            raise ValidationError({
                'main_pharmacy': 'Главная аптека не может подчиняться другой аптеке'
            })
        
        # Нельзя чтобы аптека подчинялась самой себе
        if self.main_pharmacy and self.main_pharmacy.id == self.id:
            raise ValidationError({
                'main_pharmacy': 'Аптека не может подчиняться самой себе'
            })

class UserProfile(models.Model):
    # Валидатор для русских букв в ФИО
    russian_letters_validator = RegexValidator(
        regex=r'^[а-яА-ЯёЁ\s\-]+$',
        message='Разрешены только русские буквы, пробелы и дефисы'
    )
    # Связь со стандартным пользователем
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        verbose_name='Пользователь (логин)'
    )
    
    # ФИО (обязательное поле)
    full_name = models.CharField(
        'ФИО',
        max_length=150,
        validators=[russian_letters_validator],
        help_text='Введите полное ФИО на русском языке'
    )
    
    # Аптека (НЕ обязательное поле)
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        verbose_name='Аптека',
        help_text='Выберите аптеку из списка',
        null=True,  # Разрешаем NULL в базе данных
        blank=True  # Разрешаем пустое значение в формах
    )
    
    # Заведующий (галочка)
    is_manager = models.BooleanField(
        'Заведующий',
        default=False,
        help_text='Отметьте, если пользователь является заведующим аптекой'
    )
    
    # Руководитель (новая галочка)
    is_leader = models.BooleanField(
        'Руководитель',
        default=False,
        help_text='Отметьте, если пользователь является руководителем'
    )
    
    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
    
    def __str__(self):
        manager_status = " (Заведующий)" if self.is_manager else ""
        leader_status = " (Руководитель)" if self.is_leader else ""
        pharmacy_name = f" - {self.pharmacy.name}" if self.pharmacy else " - Нет аптеки"
        return f"{self.full_name}{pharmacy_name}{manager_status}{leader_status}"
    
    def username(self):
        return self.user.username
    username.short_description = 'Логин'
    
    def get_role_display(self):
        """Возвращает отображаемое название роли"""
        roles = []
        if self.is_leader:
            roles.append('Руководитель')
        if self.is_manager:
            roles.append('Заведующий')
        if not roles:
            roles.append('Сотрудник')
        return ', '.join(roles)

ATTENDANCE_CHOICES = [
    ('', '--- Выберите статус ---'),  # Пустой выбор
    ('full', 'Весь день'),
    ('half', 'Пол дня'),
    ('vacation', 'В отпуске'),
    ('sick', 'На больничном'),
]

class Attendance(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    date = models.DateField('Дата')
    status = models.CharField('Статус', max_length=10, choices=ATTENDANCE_CHOICES, blank=True)  # Разрешаем пустое значение
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        verbose_name = 'Посещаемость'
        verbose_name_plural = 'Посещаемость'
        unique_together = ['user', 'date']
    
    def __str__(self):
        if self.status:
            return f"{self.user} - {self.date} - {self.get_status_display()}"
        return f"{self.user} - {self.date} - Не указано"

class Leadership(models.Model): # рабочая модель руководители
    # Валидатор для русских букв в ФИО
    russian_letters_validator = RegexValidator(
        regex=r'^[а-яА-ЯёЁ\s\-]+$',
        message='Разрешены только русские буквы, пробелы и дефисы'
    )
    
    # Связь со стандартным пользователем
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        verbose_name='Пользователь (логин)',
        help_text='Выберите пользователя из стандартной системы авторизации'
    )
    
    # ФИО (обязательное поле)
    full_name = models.CharField(
        'ФИО руководителя',
        max_length=150,
        validators=[russian_letters_validator],
        help_text='Введите полное ФИО на русском языке'
    )
    
    # Должность (обязательное поле)
    position = models.CharField(
        'Должность',
        max_length=100,
        help_text='Введите должность руководителя'
    )
    
    class Meta:
        verbose_name = 'Руководитель'
        verbose_name_plural = 'Руководство'
    
    def __str__(self):
        return f"{self.full_name} - {self.position}"
    
    def username(self):
        return self.user.username
    username.short_description = 'Логин'    


class MyModel(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title