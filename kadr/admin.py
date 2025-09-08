from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, User
from django.contrib.auth.models import User
from .models import MyModel, Pharmacy, UserProfile, Leadership, Attendance
from django import forms

admin.site.register(MyModel)

@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'phone']
    search_fields = ['name', 'address']
    list_filter = ['name']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'username', 'pharmacy', 'is_manager', 'is_leader', 'role_display']
    list_filter = ['pharmacy', 'is_manager', 'is_leader']
    search_fields = ['full_name', 'user__username', 'pharmacy__name']
    autocomplete_fields = ['pharmacy']
    
    fieldsets = (
        ('Учетные данные', {
            'fields': ('user',)
        }),
        ('Информация о сотруднике', {
            'fields': ('full_name', 'pharmacy')
        }),
        ('Роли пользователя', {
            'fields': ('is_manager', 'is_leader'),
            'description': 'Определите роли пользователя в системе'
        }),
    )
    
    def role_display(self, obj):
        return obj.get_role_display()
    role_display.short_description = 'Роль'
    
    # Действия для массового назначения ролей
    actions = ['make_leader', 'make_manager', 'remove_roles']
    
    def make_leader(self, request, queryset):
        queryset.update(is_leader=True)
        self.message_user(request, "Выбранные пользователи назначены руководителями")
    make_leader.short_description = "Назначить руководителями"
    
    def make_manager(self, request, queryset):
        queryset.update(is_manager=True)
        self.message_user(request, "Выбранные пользователи назначены заведующими")
    make_manager.short_description = "Назначить заведующими"
    
    def remove_roles(self, request, queryset):
        queryset.update(is_manager=False, is_leader=False)
        self.message_user(request, "Роли сняты с выбранных пользователей")
    remove_roles.short_description = "Снять все роли"

@admin.register(Leadership)
class LeadershipAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'username', 'position']
    list_filter = ['position']
    search_fields = ['full_name', 'user__username', 'position']
    
    fieldsets = (
        ('Учетные данные', {
            'fields': ('user',)
        }),
        ('Информация о руководителе', {
            'fields': ('full_name', 'position')
        }),
    )
    
    def username(self, obj):
        return obj.user.username
    username.short_description = 'Логин'
    username.admin_order_field = 'user__username'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'status', 'created_at']
    list_filter = ['date', 'status', 'user__pharmacy']
    search_fields = ['user__full_name', 'user__pharmacy__name']
    date_hierarchy = 'date'
    
    def get_readonly_fields(self, request, obj=None):
        # Запрещаем редактирование даты после создания
        if obj:
            return ['user', 'date']
        return []
