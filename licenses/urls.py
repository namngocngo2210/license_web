from django.urls import path

from . import views

app_name = 'licenses'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('tiktok/', views.dashboard_tiktok, name='dashboard_tiktok'),
    path('tiktok/<int:pk>/extend/', views.extend_tiktok_license, name='extend_tiktok'),
    path('tiktok/<int:pk>/delete/', views.delete_tiktok_license, name='delete_tiktok'),
    path('licenses/<int:pk>/extend/', views.extend_license, name='extend'),
    path('licenses/<int:pk>/delete/', views.delete_license, name='delete'),
    path('packages/', views.get_extension_packages, name='get_packages'),
    path('payment-info/', views.get_payment_info, name='get_payment_info'),
    path('qr-code/', views.generate_qr_code, name='generate_qr'),
]

