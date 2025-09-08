import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from datetime import date, timedelta, datetime
from django.db.models import Count, Q, Case, When, IntegerField
from .models import User, UserProfile,  Pharmacy, Attendance, ATTENDANCE_CHOICES
from .forms import AttendanceForm, DateRangeForm, PharmacySelectForm, LeaderDateRangeForm, MonthYearForm, LeaderTimesheetForm
from django.utils.timezone import now
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from calendar import monthrange
from dateutil.easter import easter
from dateutil.relativedelta import relativedelta
from .utils import get_working_days, RussianHolidays
from django.template.loader import render_to_string

def home(request):
    """Главная страница - перенаправляет аутентифицированных пользователей"""
    if request.user.is_authenticated:
        return redirect_based_on_role(request)
    else:
        return redirect('login')

def custom_logout(request):
    logout(request)
    return redirect('login')

@csrf_exempt
def ajax_login(request):
    """Ajax авторизация"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                return JsonResponse({
                    'success': True,
                    'redirect_url': '/redirect/'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Неверный логин или пароль'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Ошибка сервера'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Неверный метод запроса'
    })

@require_POST
@login_required
def save_attendance_ajax(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        status = data.get('status')
        
        print(f"Received data: user_id={user_id}, status={status}")  # Для отладки
        
        if not all([user_id, status]):
            return JsonResponse({'success': False, 'error': 'Не все данные предоставлены'})
        
        # Используем сегодняшнюю дату
        date = timezone.now().date()
        
        # Получаем UserProfile вместо User
        try:
            user_profile = UserProfile.objects.get(user__id=user_id)
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Профиль пользователя не найден'})
        
        # Создаем или обновляем запись посещаемости
        attendance, created = Attendance.objects.update_or_create(
            user=user_profile,  # Теперь передаем UserProfile
            date=date,
            defaults={'status': status}
        )
        
        return JsonResponse({
            'success': True,
            'status': attendance.status,
            'status_display': attendance.get_status_display(),
            'created': created
        })
        
    except Exception as e:
        print(f"Error in save_attendance_ajax: {e}")  # Для отладки
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def redirect_based_on_role(request):
    """Перенаправляет пользователя в зависимости от роли"""
    try:
        # Проверяем, существует ли профиль
        if not hasattr(request.user, 'userprofile'):
            return redirect('access_denied')
            
        profile = request.user.userprofile
        
        # Проверяем роли в порядке приоритета
        if profile.is_manager:
            return redirect('manager_dashboard')
        elif profile.is_leader:
            return redirect('leader_statistics')
        else:
            # Все остальные - обычные сотрудники
            return redirect('statistics_employee')
            
    except Exception as e:
        # Логируем ошибку для debugging
        print(f"Redirect error: {e}")
        return redirect('access_denied')

@login_required
def manager_dashboard(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not profile.is_manager:
            return redirect('access_denied')
        
        today = date.today()
        
        # Получаем все аптеки: основная и все подчиненные
        main_pharmacy = profile.pharmacy
        branch_pharmacies = Pharmacy.objects.filter(main_pharmacy=main_pharmacy)
        all_pharmacies = [main_pharmacy] + list(branch_pharmacies)
        
        # Получаем всех сотрудников всех аптек
        employees = UserProfile.objects.filter(pharmacy__in=all_pharmacies)
        
        # Создаем или получаем записи посещаемости на сегодня с ПУСТЫМ статусом
        for employee in employees:
            Attendance.objects.get_or_create(
                user=employee,
                date=today,
                defaults={'status': ''}  # Пустой статус по умолчанию
            )
        
        # Получаем актуальные данные на сегодня
        attendances = Attendance.objects.filter(
            user__in=employees,
            date=today
        ).select_related('user', 'user__pharmacy')
        
        # Группируем сотрудников по аптекам
        pharmacy_groups = {}
        for attendance in attendances:
            pharmacy = attendance.user.pharmacy
            if pharmacy not in pharmacy_groups:
                pharmacy_groups[pharmacy] = []
            pharmacy_groups[pharmacy].append(attendance)
        
        # Создаем формы для каждого сотрудника
        forms_data = []
        for pharmacy, pharmacy_attendances in pharmacy_groups.items():
            pharmacy_forms = []
            for attendance in pharmacy_attendances:
                form = AttendanceForm(instance=attendance, prefix=str(attendance.user.id))
                pharmacy_forms.append((attendance.user, form, attendance))
            forms_data.append((pharmacy, pharmacy_forms))
        
        # Сортируем: сначала главная аптека, потом подчиненные
        forms_data.sort(key=lambda x: (x[0] != main_pharmacy, x[0].name))
        
        if request.method == 'POST':
            if 'save_status' in request.POST:
                user_id = request.POST.get('user_id')
                try:
                    attendance = Attendance.objects.get(
                        user_id=user_id,
                        date=today
                    )
                    form = AttendanceForm(request.POST, instance=attendance, prefix=user_id)
                    if form.is_valid():
                        form.save()
                        print(f"Status saved for user {user_id}: {form.cleaned_data['status']}")
                        return redirect('manager_dashboard')
                    else:
                        print("Form errors:", form.errors)
                except Exception as e:
                    print(f"Error: {e}")
        
        context = {
            'pharmacy_groups': forms_data,
            'main_pharmacy': main_pharmacy,
            'branch_pharmacies': branch_pharmacies,
            'pharmacy': profile.pharmacy,
            'today': today,
        }
        return render(request, 'manager_dashboard.html', context)
    
    except UserProfile.DoesNotExist:
        return redirect('access_denied')

@login_required
def statistics(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not profile.is_manager:
            return redirect('access_denied')
        
        today = date.today()
        
        # Обработка периода как у руководителей
        if 'current_month' in request.GET:
            first_day = date(today.year, today.month, 1)
            start_date = first_day
            end_date = today
        elif 'current_week' in request.GET:
            monday = today - timedelta(days=today.weekday())
            start_date = monday
            end_date = today
        elif 'current_day' in request.GET:
            start_date = today
            end_date = today
        else:
            # Ручной выбор дат или по умолчанию
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            
            if start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    # По умолчанию - текущий месяц
                    first_day = date(today.year, today.month, 1)
                    start_date = first_day
                    end_date = today
            else:
                # По умолчанию - текущий месяц
                first_day = date(today.year, today.month, 1)
                start_date = first_day
                end_date = today
        
        # Если дата начала позже даты окончания - меняем местами
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        # Инициализируем форму с текущими датами
        form = DateRangeForm(initial={
            'start_date': start_date,
            'end_date': end_date
        })
        
        # Получаем все аптеки: основная и все подчиненные
        main_pharmacy = profile.pharmacy
        branch_pharmacies = Pharmacy.objects.filter(main_pharmacy=main_pharmacy)
        all_pharmacies = [main_pharmacy] + list(branch_pharmacies)
        
        # Получаем всех сотрудников всех аптек
        employees = UserProfile.objects.filter(pharmacy__in=all_pharmacies)
        
        # Функция для подсчета рабочих дней (исключая выходные и праздники)
        def get_working_days_count(start, end):
            working_days = 0
            current_date = start
            
            while current_date <= end:
                if RussianHolidays.is_working_day(current_date):
                    working_days += 1
                current_date += timedelta(days=1)
            
            return working_days
        
        # Подсчитываем рабочие дни для всего периода
        total_working_days = get_working_days_count(start_date, end_date)
        
        # Группируем статистику по аптекам
        pharmacy_stats = []
        total_stats = {choice[0]: 0 for choice in ATTENDANCE_CHOICES}
        total_employees_count = 0
        
        for pharmacy in all_pharmacies:
            # Сотрудники текущей аптеки
            pharmacy_employees = employees.filter(pharmacy=pharmacy)
            total_employees_count += pharmacy_employees.count()
            
            # Статистика для текущей аптеки
            pharmacy_employee_stats = []
            pharmacy_total_stats = {choice[0]: 0 for choice in ATTENDANCE_CHOICES}
            
            for employee in pharmacy_employees:
                # Получаем все записи посещаемости сотрудника за период
                attendances = Attendance.objects.filter(
                    user=employee,
                    date__range=[start_date, end_date]
                ).order_by('date')
                
                # Считаем статистику по статусам
                status_counts = {choice[0]: 0 for choice in ATTENDANCE_CHOICES}
                for attendance in attendances:
                    if attendance.status and RussianHolidays.is_working_day(attendance.date):  # Учитываем только рабочие дни
                        status_counts[attendance.status] += 1
                        pharmacy_total_stats[attendance.status] += 1
                        total_stats[attendance.status] += 1
                
                # Считаем количество рабочих дней для сотрудника
                employee_working_days = get_working_days_count(start_date, end_date)
                missing_days = employee_working_days - sum(status_counts.values())
                
                pharmacy_employee_stats.append({
                    'employee': employee,
                    'attendances': attendances,
                    'status_counts': status_counts,
                    'total_working_days': employee_working_days,
                    'missing_days': missing_days,
                    'attendance_percentage': (sum(status_counts.values()) / employee_working_days * 100) if employee_working_days > 0 else 0
                })
            
            pharmacy_stats.append({
                'pharmacy': pharmacy,
                'employee_stats': pharmacy_employee_stats,
                'total_stats': pharmacy_total_stats,
                'employees_count': pharmacy_employees.count(),
                'is_main': pharmacy == main_pharmacy
            })
        
        # Сортируем: сначала главная аптека, потом подчиненные
        pharmacy_stats.sort(key=lambda x: not x['is_main'])
        
        context = {
            'form': form,
            'start_date': start_date,
            'end_date': end_date,
            'pharmacy_stats': pharmacy_stats,
            'total_stats': total_stats,
            'total_employees_count': total_employees_count,
            'main_pharmacy': main_pharmacy,
            'attendance_choices': ATTENDANCE_CHOICES,
            'total_working_days': total_working_days,
            'today': today,
        }
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Для AJAX запросов возвращаем JSON с данными для обновления
            from django.http import JsonResponse
            from django.template.loader import render_to_string
            
            # Рендерим HTML контент
            html_content = render_to_string('includes/manager_statistics_results.html', context)
            
            return JsonResponse({
                'success': True,
                'html': html_content,
                'period_text': f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
                'total_working_days': total_working_days
            })
        else:
            # Для обычных запросов возвращаем полную страницу
            return render(request, 'statistics.html', context)
    
    except UserProfile.DoesNotExist:
        return redirect('access_denied')


@login_required
@csrf_exempt
def statistics_ajax(request):
    """AJAX обработчик для статистики заведующих"""
    return statistics(request)

@login_required
def statistics_employee(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
                
        today = date.today()
        
        # Обработка периода
        if 'current_month' in request.GET:
            first_day = date(today.year, today.month, 1)
            start_date = first_day
            end_date = today
            period_type = 'month'
        elif 'current_week' in request.GET:
            monday = today - timedelta(days=today.weekday())
            start_date = monday
            end_date = today
            period_type = 'week'
        elif 'current_day' in request.GET:
            start_date = today
            end_date = today
            period_type = 'day'
        else:
            # Ручной выбор дат или по умолчанию
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            
            if start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    period_type = 'custom'
                except (ValueError, TypeError):
                    # По умолчанию - текущий день
                    start_date = today
                    end_date = today
                    period_type = 'day'
            else:
                # По умолчанию - текущий день
                start_date = today
                end_date = today
                period_type = 'day'
        
        # Если дата начала позже даты окончания - меняем местами
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        # Инициализируем форму с текущими датами
        form = DateRangeForm(initial={
            'start_date': start_date,
            'end_date': end_date
        })
        
        # ТОЛЬКО ТЕКУЩИЙ СОТРУДНИК
        employee = profile
        
        # Функция для подсчета рабочих дней (исключая выходные и праздники)
        def get_working_days_count(start, end):
            working_days = 0
            current_date = start
            
            while current_date <= end:
                if RussianHolidays.is_working_day(current_date):
                    working_days += 1
                current_date += timedelta(days=1)
            
            return working_days
        
        # Подсчитываем рабочие дни для периода
        total_working_days = get_working_days_count(start_date, end_date)
        
        # Получаем все записи посещаемости сотрудника за период
        attendances = Attendance.objects.filter(
            user=employee,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Считаем статистику по статусам (только для рабочих дней)
        status_counts = {choice[0]: 0 for choice in ATTENDANCE_CHOICES}
        for attendance in attendances:
            if attendance.status and RussianHolidays.is_working_day(attendance.date):
                status_counts[attendance.status] += 1
        
        # Считаем пропущенные рабочие дни
        missing_days = total_working_days - sum(status_counts.values())
        
        # Создаем статистику только для одного сотрудника
        employee_stats = [{
            'employee': employee,
            'attendances': attendances,
            'status_counts': status_counts,
            'total_working_days': total_working_days,
            'missing_days': missing_days,
            'attendance_percentage': (sum(status_counts.values()) / total_working_days * 100) if total_working_days > 0 else 0
        }]
        
        context = {
            'form': form,
            'start_date': start_date,
            'end_date': end_date,
            'employee_stats': employee_stats,
            'total_stats': status_counts,
            'employees_count': 1,
            'pharmacy': profile.pharmacy,
            'attendance_choices': ATTENDANCE_CHOICES,
            'total_working_days': total_working_days,
            'today': today,
            'is_manager': profile.is_manager,
            'page_title': "Моя статистика посещаемости",
        }
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Для AJAX запросов возвращаем JSON
            from django.http import JsonResponse
            from django.template.loader import render_to_string
            
            # Рендерим HTML контент
            html_content = render_to_string('statistics_employee.html', context)
            
            return JsonResponse({
                'success': True,
                'html': html_content,
                'period_text': f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_working_days': total_working_days
            })
        else:
            # Для обычных запросов возвращаем полную страницу
            return render(request, 'statistics_employee.html', context)
    
    except UserProfile.DoesNotExist:
        return redirect('access_denied')

@login_required
def leader_statistics(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not profile.is_leader:
            return redirect('access_denied')
        
        today = date.today()
        
        # Получаем ID выбранной аптеки из GET параметров
        pharmacy_id = request.GET.get('pharmacy') or request.POST.get('pharmacy')
        selected_pharmacy = None
        if pharmacy_id:
            try:
                selected_pharmacy = Pharmacy.objects.get(id=pharmacy_id)
            except Pharmacy.DoesNotExist:
                pass
        
        # Инициализируем форму с выбранной аптекой
        pharmacy_form = PharmacySelectForm(initial={'pharmacy': selected_pharmacy} if selected_pharmacy else None)
        
        # Обработка периода
        if 'current_day' in request.GET or 'current_day' in request.POST:
            start_date = today
            end_date = today
        elif 'current_week' in request.GET or 'current_week' in request.POST:
            monday = today - timedelta(days=today.weekday())
            start_date = monday
            end_date = today
        elif 'current_month' in request.GET or 'current_month' in request.POST:
            first_day = date(today.year, today.month, 1)
            start_date = first_day
            end_date = today
        else:
            # Ручной выбор дат или по умолчанию
            start_date_str = request.GET.get('start_date') or request.POST.get('start_date')
            end_date_str = request.GET.get('end_date') or request.POST.get('end_date')
            
            if start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    # По умолчанию - текущий месяц
                    first_day = date(today.year, today.month, 1)
                    start_date = first_day
                    end_date = today
            else:
                # По умолчанию - текущий месяц
                first_day = date(today.year, today.month, 1)
                start_date = first_day
                end_date = today
        
        # Если дата начала позже даты окончания - меняем местами
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        # Рассчитываем рабочие дни для периода
        working_days_count = 0
        current_date = start_date
        while current_date <= end_date:
            if RussianHolidays.is_working_day(current_date):
                working_days_count += 1
            current_date += timedelta(days=1)
        
        # Если аптека выбрана, получаем статистику
        employee_stats = []
        pharmacy_stats = {
            'total_employees': 0,
            'total_days': working_days_count,
            'status_counts': {'full': 0, 'half': 0, 'vacation': 0, 'sick': 0},
            'attendance_percentage': 0
        }
        
        if selected_pharmacy:
            # Получаем всех сотрудников выбранной аптеки
            employees = UserProfile.objects.filter(pharmacy=selected_pharmacy)
            pharmacy_stats['total_employees'] = employees.count()
            
            total_attendances = 0
            total_possible_days = 0
            
            # Собираем статистику по каждому сотруднику
            for employee in employees:
                # Получаем все записи посещаемости сотрудника за период
                attendances = Attendance.objects.filter(
                    user=employee,
                    date__range=[start_date, end_date]
                ).order_by('date')
                
                # Считаем только рабочие дни с заполненными статусами
                filled_working_days = 0
                status_counts = {'full': 0, 'half': 0, 'vacation': 0, 'sick': 0}
                
                for attendance in attendances:
                    # Проверяем, что это рабочий день и статус заполнен
                    if (attendance.status and 
                        attendance.status in status_counts and 
                        RussianHolidays.is_working_day(attendance.date)):
                        status_counts[attendance.status] += 1
                        pharmacy_stats['status_counts'][attendance.status] += 1
                        filled_working_days += 1
                
                total_attendances += filled_working_days
                total_possible_days += working_days_count
                
                employee_stats.append({
                    'employee': employee,
                    'status_counts': status_counts,
                    'total_days': working_days_count,
                    'missing_days': working_days_count - filled_working_days,
                    'attendance_count': filled_working_days,
                    'attendance_percentage': (filled_working_days / working_days_count * 100) if working_days_count > 0 else 0
                })
            
            # Общий процент присутствия по аптеке
            if total_possible_days > 0:
                pharmacy_stats['attendance_percentage'] = (total_attendances / total_possible_days * 100)
        
        context = {
            'pharmacy_form': pharmacy_form,
            'start_date': start_date,
            'end_date': end_date,
            'employee_stats': employee_stats,
            'pharmacy_stats': pharmacy_stats,
            'selected_pharmacy': selected_pharmacy,
            'today': today,
            'working_days_count': working_days_count,
        }
        
        # Если это AJAX запрос, возвращаем JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html_content = render_to_string('includes/leader_statistics_results.html', context)
            return JsonResponse({
                'success': True,
                'html': html_content,
                'pharmacy_name': selected_pharmacy.name if selected_pharmacy else None,
                'has_data': bool(selected_pharmacy and employee_stats)
            })
        
        return render(request, 'leader_statistics.html', context)
    
    except UserProfile.DoesNotExist:
        return redirect('access_denied')


@login_required
@csrf_exempt
def leader_statistics_ajax(request):
    """AJAX обработчик для статистики"""
    return leader_statistics(request)


@login_required
@csrf_exempt
def leader_statistics_ajax(request):
    """AJAX обработчик для статистики"""
    return leader_statistics(request)

@login_required
def manager_timesheet(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not profile.is_manager:
            return redirect('access_denied')
        
        today = timezone.now().date()
        
        # Обработка формы выбора месяца и года
        if request.method == 'POST':
            form = MonthYearForm(request.POST)
        else:
            # По умолчанию текущий месяц и год
            form = MonthYearForm(initial={
                'year': today.year,
                'month': today.month
            })
        
        # Устанавливаем значения по умолчанию
        selected_year = today.year
        selected_month = today.month
        
        if form.is_valid():
            selected_year = form.cleaned_data['year']
            selected_month = form.cleaned_data['month']
        
        # Определяем первый и последний день месяца
        first_day = date(selected_year, selected_month, 1)
        last_day = date(selected_year, selected_month, monthrange(selected_year, selected_month)[1])
        
        # Получаем рабочие и нерабочие дни
        working_days, non_working_days = get_working_days(selected_year, selected_month)
        working_days_set = set(working_days)
        
        # Получаем все аптеки: основная и подчиненные
        main_pharmacy = profile.pharmacy
        branch_pharmacies = Pharmacy.objects.filter(main_pharmacy=main_pharmacy)
        all_pharmacies = [main_pharmacy] + list(branch_pharmacies)
        
        # Собираем данные для табеля
        timesheet_data = []
        
        for pharmacy in all_pharmacies:
            # Получаем сотрудников аптеки
            employees = UserProfile.objects.filter(pharmacy=pharmacy).order_by('user__last_name')
            
            pharmacy_data = {
                'pharmacy': pharmacy,
                'is_main': pharmacy == main_pharmacy,
                'employees': []
            }
            
            for employee in employees:
                # Получаем посещаемость сотрудника за месяц
                attendances = Attendance.objects.filter(
                    user=employee,
                    date__range=[first_day, last_day]
                ).order_by('date')
                
                # Создаем список статусов для каждого дня
                daily_status = []
                attendance_dict = {att.date.day: att.status for att in attendances}
                
                for day in range(1, last_day.day + 1):
                    current_date = date(selected_year, selected_month, day)
                    
                    # Проверяем, рабочий ли это день
                    if day in working_days_set:
                        # Рабочий день - показываем статус посещения
                        status = attendance_dict.get(day)
                        daily_status.append({
                            'status': status,
                            'is_working': True,
                            'is_weekend': False,
                            'is_holiday': False
                        })
                    else:
                        # Нерабочий день - автоматически заполняем
                        is_weekend = RussianHolidays.is_weekend(current_date)
                        is_holiday = RussianHolidays.is_holiday(current_date)
                        
                        daily_status.append({
                            'status': 'weekend' if is_weekend else 'holiday',
                            'is_working': False,
                            'is_weekend': is_weekend,
                            'is_holiday': is_holiday
                        })
                
                # Считаем только рабочие дни для статистики
                total_working_days = len(working_days_set)
                filled_working_days = sum(1 for day_status in daily_status 
                                        if day_status['is_working'] and day_status['status'] is not None)
                
                # Создаем данные для сотрудника
                employee_data = {
                    'employee': employee,
                    'daily_status': daily_status,
                    'total_days': (last_day - first_day).days + 1,
                    'total_working_days': total_working_days,
                    'filled_working_days': filled_working_days,
                    'attendance_percentage': (filled_working_days / total_working_days * 100) if total_working_days > 0 else 0
                }
                
                pharmacy_data['employees'].append(employee_data)
            
            timesheet_data.append(pharmacy_data)
        
        # Генерируем список дней месяца
        days_in_month = list(range(1, last_day.day + 1))
        
        # Получаем название месяца на русском
        month_names = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        selected_month_name = month_names.get(selected_month, '')
        
        context = {
            'form': form,
            'timesheet_data': timesheet_data,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'selected_month_name': selected_month_name,
            'days_in_month': days_in_month,
            'working_days_set': working_days_set,
            'non_working_days': non_working_days,
            'first_day': first_day,
            'last_day': last_day,
            'main_pharmacy': main_pharmacy,
        }
        
        return render(request, 'manager_timesheet.html', context)
    
    except UserProfile.DoesNotExist:
        return redirect('access_denied')

@login_required
@csrf_exempt
def leader_timesheet_report_ajax(request):
    """AJAX обработчик для загрузки табелей"""
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not (profile.is_leader or profile.is_operator):
            return JsonResponse({'success': False, 'error': 'Доступ запрещен'})
        
        today = timezone.now().date()
        
        # Обрабатываем POST данные
        selected_year = int(request.POST.get('year', today.year))
        selected_month = int(request.POST.get('month', today.month))
        period_type = request.POST.get('period_type', 'month')
        pharmacy_id = request.POST.get('pharmacy')
        
        timesheet_data = []
        working_days_set = set()
        days_in_month = []
        selected_pharmacy = None
        
        if pharmacy_id:
            try:
                selected_pharmacy = Pharmacy.objects.get(id=pharmacy_id)
                
                if period_type == 'month':
                    # Обработка месяца
                    first_day = date(selected_year, selected_month, 1)
                    last_day = date(selected_year, selected_month, monthrange(selected_year, selected_month)[1])
                    
                    working_days, non_working_days = get_working_days(selected_year, selected_month)
                    working_days_set = set(working_days)
                    days_in_month = list(range(1, last_day.day + 1))
                    
                    employees = UserProfile.objects.filter(pharmacy=selected_pharmacy).order_by('user__last_name')
                    
                    pharmacy_data = {
                        'pharmacy': selected_pharmacy,
                        'is_main': selected_pharmacy.main_pharmacy is None,
                        'employees': [],
                        'period': f"{first_day.strftime('%d.%m.%Y')} - {last_day.strftime('%d.%m.%Y')}"
                    }
                    
                    for employee in employees:
                        attendances = Attendance.objects.filter(
                            user=employee,
                            date__range=[first_day, last_day]
                        ).order_by('date')
                        
                        daily_status = []
                        attendance_dict = {att.date.day: att.status for att in attendances}
                        
                        for day in range(1, last_day.day + 1):
                            current_date = date(selected_year, selected_month, day)
                            
                            if day in working_days_set:
                                status = attendance_dict.get(day)
                                daily_status.append({
                                    'status': status,
                                    'is_working': True,
                                    'is_weekend': False,
                                    'is_holiday': False
                                })
                            else:
                                is_weekend = RussianHolidays.is_weekend(current_date)
                                is_holiday = RussianHolidays.is_holiday(current_date)
                                daily_status.append({
                                    'status': 'weekend' if is_weekend else 'holiday',
                                    'is_working': False,
                                    'is_weekend': is_weekend,
                                    'is_holiday': is_holiday
                                })
                        
                        total_working_days = len(working_days_set)
                        filled_working_days = sum(1 for day_status in daily_status 
                                                if day_status['is_working'] and day_status['status'] is not None)
                        
                        employee_data = {
                            'employee': employee,
                            'daily_status': daily_status,
                            'total_working_days': total_working_days,
                            'filled_working_days': filled_working_days,
                            'attendance_percentage': (filled_working_days / total_working_days * 100) if total_working_days > 0 else 0
                        }
                        
                        pharmacy_data['employees'].append(employee_data)
                    
                    timesheet_data.append(pharmacy_data)
                    
                else:
                    # Обработка года
                    for month in range(1, 13):
                        if selected_year == today.year and month > today.month:
                            break
                        
                        first_day = date(selected_year, month, 1)
                        last_day = date(selected_year, month, monthrange(selected_year, month)[1])
                        
                        working_days, non_working_days = get_working_days(selected_year, month)
                        current_working_days_set = set(working_days)
                        current_days_in_month = list(range(1, last_day.day + 1))
                        
                        employees = UserProfile.objects.filter(pharmacy=selected_pharmacy).order_by('user__last_name')
                        
                        month_names = {
                            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
                        }
                        
                        pharmacy_data = {
                            'pharmacy': selected_pharmacy,
                            'is_main': selected_pharmacy.main_pharmacy is None,
                            'employees': [],
                            'period': f"{month_names[month]} {selected_year}",
                            'month_number': month,
                            'working_days_set': current_working_days_set,
                            'days_in_month': current_days_in_month
                        }
                        
                        for employee in employees:
                            attendances = Attendance.objects.filter(
                                user=employee,
                                date__range=[first_day, last_day]
                            ).order_by('date')
                            
                            daily_status = []
                            attendance_dict = {att.date.day: att.status for att in attendances}
                            
                            for day in range(1, last_day.day + 1):
                                current_date = date(selected_year, month, day)
                                
                                if day in current_working_days_set:
                                    status = attendance_dict.get(day)
                                    daily_status.append({
                                        'status': status,
                                        'is_working': True,
                                        'is_weekend': False,
                                        'is_holiday': False
                                    })
                                else:
                                    is_weekend = RussianHolidays.is_weekend(current_date)
                                    is_holiday = RussianHolidays.is_holiday(current_date)
                                    daily_status.append({
                                        'status': 'weekend' if is_weekend else 'holiday',
                                        'is_working': False,
                                        'is_weekend': is_weekend,
                                        'is_holiday': is_holiday
                                    })
                            
                            total_working_days = len(current_working_days_set)
                            filled_working_days = sum(1 for day_status in daily_status 
                                                    if day_status['is_working'] and day_status['status'] is not None)
                            
                            employee_data = {
                                'employee': employee,
                                'daily_status': daily_status,
                                'total_working_days': total_working_days,
                                'filled_working_days': filled_working_days,
                                'attendance_percentage': (filled_working_days / total_working_days * 100) if total_working_days > 0 else 0
                            }
                            
                            pharmacy_data['employees'].append(employee_data)
                        
                        timesheet_data.append(pharmacy_data)
                        
            except Pharmacy.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Аптека не найдена'})
        
        # Рендерим HTML шаблон
        html_content = render_to_string('includes/timesheet_results.html', {
            'timesheet_data': timesheet_data,
            'period_type': period_type,
            'working_days_set': working_days_set,
            'days_in_month': days_in_month,
        })
        
        return JsonResponse({
            'success': True,
            'html': html_content,
            'pharmacy_name': selected_pharmacy.name if selected_pharmacy else ''
        })
        
    except Exception as e:
        import traceback
        print(f"Error in AJAX view: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def leader_timesheet_report(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not (profile.is_leader or profile.is_operator):
            return redirect('access_denied')
        
        today = timezone.now().date()
        
        # Форма выбора аптеки и периода
        if request.method == 'POST':
            form = LeaderTimesheetForm(request.POST, user=request.user)
        else:
            form = LeaderTimesheetForm(user=request.user, initial={
                'year': today.year,
                'month': today.month,
                'period_type': 'month'
            })
        
        # Устанавливаем значения по умолчанию
        selected_year = today.year
        selected_month = today.month
        selected_pharmacy = None
        period_type = 'month'
        timesheet_data = []
        working_days_set = set()
        days_in_month = []
        
        if form.is_valid():
            selected_year = form.cleaned_data['year']
            selected_month = form.cleaned_data['month']
            selected_pharmacy = form.cleaned_data['pharmacy']
            period_type = form.cleaned_data['period_type']
        
        # Получаем данные в зависимости от типа периода
        if selected_pharmacy:
            if period_type == 'month':
                # Режим месяца
                first_day = date(selected_year, selected_month, 1)
                last_day = date(selected_year, selected_month, monthrange(selected_year, selected_month)[1])
                
                working_days, non_working_days = get_working_days(selected_year, selected_month)
                working_days_set = set(working_days)
                days_in_month = list(range(1, last_day.day + 1))
                
                # Получаем сотрудников выбранной аптеки
                employees = UserProfile.objects.filter(pharmacy=selected_pharmacy).order_by('user__last_name')
                
                pharmacy_data = {
                    'pharmacy': selected_pharmacy,
                    'is_main': selected_pharmacy.main_pharmacy is None,
                    'employees': [],
                    'period': f"{first_day.strftime('%d.%m.%Y')} - {last_day.strftime('%d.%m.%Y')}"
                }
                
                for employee in employees:
                    attendances = Attendance.objects.filter(
                        user=employee,
                        date__range=[first_day, last_day]
                    ).order_by('date')
                    
                    daily_status = []
                    attendance_dict = {att.date.day: att.status for att in attendances}
                    
                    for day in range(1, last_day.day + 1):
                        current_date = date(selected_year, selected_month, day)
                        
                        if day in working_days_set:
                            status = attendance_dict.get(day)
                            daily_status.append({
                                'status': status,
                                'is_working': True,
                                'is_weekend': False,
                                'is_holiday': False
                            })
                        else:
                            is_weekend = RussianHolidays.is_weekend(current_date)
                            is_holiday = RussianHolidays.is_holiday(current_date)
                            daily_status.append({
                                'status': 'weekend' if is_weekend else 'holiday',
                                'is_working': False,
                                'is_weekend': is_weekend,
                                'is_holiday': is_holiday
                            })
                    
                    total_working_days = len(working_days_set)
                    filled_working_days = sum(1 for day_status in daily_status 
                                            if day_status['is_working'] and day_status['status'] is not None)
                    
                    employee_data = {
                        'employee': employee,
                        'daily_status': daily_status,
                        'total_working_days': total_working_days,
                        'filled_working_days': filled_working_days,
                        'attendance_percentage': (filled_working_days / total_working_days * 100) if total_working_days > 0 else 0
                    }
                    
                    pharmacy_data['employees'].append(employee_data)
                
                timesheet_data.append(pharmacy_data)
                
            else:
                # Режим года - показываем все месяцы с января по текущий
                for month in range(1, 13):
                    if selected_year == today.year and month > today.month:
                        break  # Не показываем будущие месяцы
                    
                    first_day = date(selected_year, month, 1)
                    last_day = date(selected_year, month, monthrange(selected_year, month)[1])
                    
                    working_days, non_working_days = get_working_days(selected_year, month)
                    current_working_days_set = set(working_days)
                    current_days_in_month = list(range(1, last_day.day + 1))
                    
                    employees = UserProfile.objects.filter(pharmacy=selected_pharmacy).order_by('user__last_name')
                    
                    # Получаем название месяца
                    month_names = {
                        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
                    }
                    
                    pharmacy_data = {
                        'pharmacy': selected_pharmacy,
                        'is_main': selected_pharmacy.main_pharmacy is None,
                        'employees': [],
                        'period': f"{month_names[month]} {selected_year}",
                        'month_number': month,
                        'year': selected_year,
                        'working_days_set': current_working_days_set,
                        'days_in_month': current_days_in_month
                    }
                    
                    for employee in employees:
                        attendances = Attendance.objects.filter(
                            user=employee,
                            date__range=[first_day, last_day]
                        ).order_by('date')
                        
                        daily_status = []
                        attendance_dict = {att.date.day: att.status for att in attendances}
                        
                        for day in range(1, last_day.day + 1):
                            current_date = date(selected_year, month, day)
                            
                            if day in current_working_days_set:
                                status = attendance_dict.get(day)
                                daily_status.append({
                                    'status': status,
                                    'is_working': True,
                                    'is_weekend': False,
                                    'is_holiday': False
                                })
                            else:
                                is_weekend = RussianHolidays.is_weekend(current_date)
                                is_holiday = RussianHolidays.is_holiday(current_date)
                                daily_status.append({
                                    'status': 'weekend' if is_weekend else 'holiday',
                                    'is_working': False,
                                    'is_weekend': is_weekend,
                                    'is_holiday': is_holiday
                                })
                        
                        total_working_days = len(current_working_days_set)
                        filled_working_days = sum(1 for day_status in daily_status 
                                                if day_status['is_working'] and day_status['status'] is not None)
                        
                        employee_data = {
                            'employee': employee,
                            'daily_status': daily_status,
                            'total_working_days': total_working_days,
                            'filled_working_days': filled_working_days,
                            'attendance_percentage': (filled_working_days / total_working_days * 100) if total_working_days > 0 else 0
                        }
                        
                        pharmacy_data['employees'].append(employee_data)
                    
                    timesheet_data.append(pharmacy_data)
        
        month_names = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        
        # Создаем контекст
        context = {
            'form': form,
            'timesheet_data': timesheet_data,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'selected_month_name': month_names.get(selected_month, ''),
            'period_type': period_type,
            'month_names': month_names,
            'today': today,
        }
        
        # Добавляем переменные для месячного режима
        if period_type == 'month' and timesheet_data:
            context['working_days_set'] = working_days_set
            context['days_in_month'] = days_in_month
        
        return render(request, 'leader_timesheet_report.html', context)
    
    except UserProfile.DoesNotExist:
        return redirect('access_denied')

def access_denied(request):
    return render(request, 'access_denied.html')

