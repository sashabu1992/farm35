from django.urls import path
from . import views  # Импорт views вашего приложения

urlpatterns = [
    path('ajax-login/', views.ajax_login, name='ajax_login'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('redirect/', views.redirect_based_on_role, name='redirect_based_on_role'),
    path('statistics/', views.statistics, name='statistics'),
    path('manager/statistics/ajax/', views.statistics_ajax, name='statistics_ajax'),
    path('access-denied/', views.access_denied, name='access_denied'),
    path('accounts/logout/', views.custom_logout, name='custom_logout'),
    path('employee-statistics/', views.statistics_employee, name='statistics_employee'),
    path('leader-statistics/', views.leader_statistics, name='leader_statistics'),
    path('leader/statistics/ajax/', views.leader_statistics_ajax, name='leader_statistics_ajax'),
    path('attendance/ajax/save/', views.save_attendance_ajax, name='save_attendance_ajax'),
    path('manager/timesheet/', views.manager_timesheet, name='manager_timesheet'),
    path('leader/timesheet-report/', views.leader_timesheet_report, name='leader_timesheet_report'),
    path('leader/timesheet-report/ajax/', views.leader_timesheet_report_ajax, name='leader_timesheet_report_ajax'),
]