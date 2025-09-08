# your_app/management/commands/generate_test_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random
from kadr.models import Pharmacy, UserProfile, Attendance


class Command(BaseCommand):
    help = 'Генерация тестовых данных для аптек и посещаемости'

    def handle(self, *args, **options):
        self.stdout.write('Создание тестовых данных...')

        # Очистка старых данных в правильном порядке
        Attendance.objects.all().delete()
        UserProfile.objects.all().delete()
        User.objects.filter(
            username__in=['leader', 'manager_1', 'manager_2', 'manager_3', 'manager_4', 'manager_5', 'manager_6',
                          'manager_7']).delete()
        User.objects.filter(username__startswith='employee_').delete()
        Pharmacy.objects.all().delete()

        # Создание главной аптеки
        main_pharmacy = Pharmacy.objects.create(
            name='Аптека №1 (Главная)',
            address='ул. Центральная, д. 1',
            phone='+79990000001',
            is_main=True
        )
        self.stdout.write(f'Создана главная аптека: {main_pharmacy}')

        # Создание аптечных пунктов (6 штук)
        branch_pharmacies = []
        for i in range(1, 7):
            pharmacy = Pharmacy.objects.create(
                name=f'Аптека №{i + 1} (Филиал)',
                address=f'ул. Филиальная, д. {i}',
                phone=f'+7999000001{i}',
                is_main=False,
                main_pharmacy=main_pharmacy
            )
            branch_pharmacies.append(pharmacy)
            self.stdout.write(f'Создан филиал: {pharmacy}')

        # Создание пользователя-руководителя
        leader_user = User.objects.create_user(
            username='leader',
            email='leader@pharmacy.ru',
            password='leader123',
            first_name='Иван',
            last_name='Петrov'
        )

        leader_profile = UserProfile.objects.create(
            user=leader_user,
            full_name='Петров Иван Сергеевич',
            is_leader=True,
            is_manager=False,
            pharmacy=None
        )
        self.stdout.write(f'Создан руководитель: {leader_profile}')

        # Создание заведующих для каждой аптеки
        managers = []
        all_pharmacies = [main_pharmacy] + branch_pharmacies

        for i, pharmacy in enumerate(all_pharmacies, 1):
            manager_user = User.objects.create_user(
                username=f'manager_{i}',
                email=f'manager{i}@pharmacy.ru',
                password=f'manager{i}123',
                first_name=f'Менеджер{i}',
                last_name='Аптечный'
            )

            manager_profile = UserProfile.objects.create(
                user=manager_user,
                full_name=f'Аптечный Менеджер {i} Иванович',
                pharmacy=pharmacy,
                is_manager=True,
                is_leader=False
            )
            managers.append(manager_profile)
            self.stdout.write(f'Создан заведующий: {manager_profile}')

        # Создание обычных сотрудников (по 2-3 на аптеку)
        employees = []
        employee_count = 1

        for pharmacy in all_pharmacies:
            for j in range(random.randint(2, 3)):
                employee_user = User.objects.create_user(
                    username=f'employee_{employee_count}',
                    email=f'employee{employee_count}@pharmacy.ru',
                    password=f'employee{employee_count}123',
                    first_name=f'Сотрудник{employee_count}',
                    last_name='Аптечный'
                )

                employee_profile = UserProfile.objects.create(
                    user=employee_user,
                    full_name=f'Аптечный Сотрудник {employee_count} Петрович',
                    pharmacy=pharmacy,
                    is_manager=False,
                    is_leader=False
                )
                employees.append(employee_profile)
                employee_count += 1
                self.stdout.write(f'Создан сотрудник: {employee_profile}')

        # УПРОЩЕННАЯ генерация данных о посещаемости (только последний месяц)
        all_users = managers + employees
        status_choices = ['full', 'half', 'vacation', 'sick', '']
        status_weights = [0.6, 0.2, 0.05, 0.05, 0.1]

        # Генерируем данные только за последний месяц (30 дней)
        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date()

        current_date = start_date
        attendance_count = 0

        # Создаем записи пакетами для оптимизации
        attendance_batch = []

        while current_date <= end_date:
            if current_date.weekday() < 5:  # Только рабочие дни
                for user_profile in all_users:
                    status = random.choices(status_choices, weights=status_weights, k=1)[0]

                    attendance_batch.append(Attendance(
                        user=user_profile,
                        date=current_date,
                        status=status
                    ))

                    attendance_count += 1

                    # Сохраняем пакетами по 100 записей
                    if len(attendance_batch) >= 100:
                        Attendance.objects.bulk_create(attendance_batch)
                        attendance_batch = []
                        self.stdout.write(f'Создано {attendance_count} записей...')

            current_date += timedelta(days=1)

        # Сохраняем оставшиеся записи
        if attendance_batch:
            Attendance.objects.bulk_create(attendance_batch)

        self.stdout.write(f'Создано {attendance_count} записей о посещаемости')

        # Вывод данных для входа
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('ДАННЫЕ ДЛЯ ВХОДА:')
        self.stdout.write('=' * 50)
        self.stdout.write('Руководитель:')
        self.stdout.write('Логин: leader')
        self.stdout.write('Пароль: leader123')
        self.stdout.write('Email: leader@pharmacy.ru')
        self.stdout.write('')

        self.stdout.write('Заведующие аптек:')
        for i in range(1, 8):
            self.stdout.write(f'Аптека {i}: логин=manager_{i}, пароль=manager{i}123')

        self.stdout.write('')
        self.stdout.write('Обычные сотрудники (первые 5):')
        for i in range(1, min(6, employee_count)):
            self.stdout.write(f'employee_{i} / employee{i}123')

        if employee_count > 6:
            self.stdout.write(f'... и еще {employee_count - 6} сотрудников')

        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('Тестовые данные успешно созданы!')
        self.stdout.write('=' * 50)