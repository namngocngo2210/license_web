from django.urls import path

from . import views

app_name = 'licenses'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('tiktok/', views.dashboard_tiktok, name='dashboard_tiktok'),
    path('tiktok/<int:pk>/delete/', views.delete_tiktok_license, name='delete_tiktok'),
    path('licenses/<int:pk>/extend/', views.extend_license, name='extend'),
    path('licenses/<int:pk>/delete/', views.delete_license, name='delete'),
]

