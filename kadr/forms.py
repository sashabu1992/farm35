from django import forms
from .models import Attendance, Pharmacy, UserProfile
from datetime import date
from django.utils import timezone

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control form-select form-select-sm status-select',
                # НЕТ disabled здесь - управляем через JS
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [('', '---------')] + list(self.fields['status'].choices)

class PharmacySelectForm(forms.Form):
    pharmacy = forms.ModelChoiceField(
        queryset=Pharmacy.objects.all(),
        label='Выберите аптеку',
        required=False,
        empty_label='Все аптеки',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class DateRangeForm(forms.Form):
    start_date = forms.DateField(
        label='Начальная дата',
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control',
            'max': timezone.now().date().isoformat()
        })
    )
    end_date = forms.DateField(
        label='Конечная дата',
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control',
            'max': timezone.now().date().isoformat()
        })
    )
class LeaderDateRangeForm(forms.Form):
    pharmacy = forms.ModelChoiceField(
        queryset=Pharmacy.objects.all(),
        label='Аптека',
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )
    start_date = forms.DateField(
        label='Начальная дата',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        label='Конечная дата', 
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

class MonthYearForm(forms.Form):
    MONTH_CHOICES = [
        (1, 'Январь'), (2, 'Февраль'), (3, 'Март'), (4, 'Апрель'),
        (5, 'Май'), (6, 'Июнь'), (7, 'Июль'), (8, 'Август'),
        (9, 'Сентябрь'), (10, 'Октябрь'), (11, 'Ноябрь'), (12, 'Декабрь')
    ]
    
    YEAR_CHOICES = [(year, year) for year in range(2020, timezone.now().year + 2)]
    
    year = forms.TypedChoiceField(  # Изменено на TypedChoiceField
        label='Год',
        choices=YEAR_CHOICES,
        initial=timezone.now().year,
        coerce=int  # Преобразует в integer
    )
    
    month = forms.TypedChoiceField(  # Изменено на TypedChoiceField
        label='Месяц',
        choices=MONTH_CHOICES,
        initial=timezone.now().month,
        coerce=int  # Преобразует в integer
    )

class LeaderTimesheetForm(forms.Form):
    PERIOD_CHOICES = [
        ('month', 'Месяц'),
        ('year', 'Год')
    ]
    
    MONTH_CHOICES = [
        (1, 'Январь'), (2, 'Февраль'), (3, 'Март'), (4, 'Апрель'),
        (5, 'Май'), (6, 'Июнь'), (7, 'Июль'), (8, 'Август'),
        (9, 'Сентябрь'), (10, 'Октябрь'), (11, 'Ноябрь'), (12, 'Декабрь')
    ]
    
    YEAR_CHOICES = [(year, year) for year in range(2020, timezone.now().year + 2)]
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Динамически заполняем выбор аптек в зависимости от прав пользователя
        if user:
            profile = UserProfile.objects.get(user=user)
            if profile.is_leader:
                # Руководитель видит все аптеки
                pharmacies = Pharmacy.objects.all()
            elif profile.is_operator:
                # Оператор видит все аптеки
                pharmacies = Pharmacy.objects.all()
            else:
                pharmacies = Pharmacy.objects.none()
            
            self.fields['pharmacy'] = forms.ModelChoiceField(
                label='Аптека',
                queryset=pharmacies,
                empty_label="Выберите аптеку",
                required=True
            )
    
    pharmacy = forms.ModelChoiceField(
        label='Аптека',
        queryset=Pharmacy.objects.none(),  # Будет заполнено динамически
        empty_label="Выберите аптеку",
        required=True
    )
    
    period_type = forms.ChoiceField(
        label='Период',
        choices=PERIOD_CHOICES,
        widget=forms.RadioSelect,
        initial='month'
    )
    
    year = forms.TypedChoiceField(
        label='Год',
        choices=YEAR_CHOICES,
        initial=timezone.now().year,
        coerce=int
    )
    
    month = forms.TypedChoiceField(
        label='Месяц',
        choices=MONTH_CHOICES,
        initial=timezone.now().month,
        coerce=int,
        required=False
    )
    
    def clean(self):
        cleaned_data = super().clean()
        period_type = cleaned_data.get('period_type')
        
        if period_type == 'month' and not cleaned_data.get('month'):
            self.add_error('month', 'Обязательно для выбора при периоде "Месяц"')
        
        return cleaned_data