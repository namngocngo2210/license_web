from django.urls import path

from . import views

app_name = 'licenses'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('licenses/<int:pk>/extend/', views.extend_license, name='extend'),
    path('licenses/<int:pk>/delete/', views.delete_license, name='delete'),
    path('verify', views.verify_license, name='verify'),
    path('create', views.create_license_api, name='create_api'),
    path('list', views.list_license_api, name='list_api'),
    path('update', views.update_license_api, name='update_api'),
    path('delete', views.delete_license_api, name='delete_api'),
    path('delete-all', views.delete_all_license_api, name='delete_all_api'),
    path('users/create', views.api_create_user, name='api_create_user'),
    path('api/packages/', views.get_extension_packages, name='get_packages'),
    path('api/payment-info/', views.get_payment_info, name='get_payment_info'),
    path('api/qr-code/', views.generate_qr_code, name='generate_qr'),
]

