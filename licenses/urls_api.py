from django.urls import path

from . import views

urlpatterns = [
    path('verify', views.verify_license, name='verify'),
    path('create', views.create_license_api, name='create_api'),
    path('list', views.list_license_api, name='list_api'),
    path('update', views.update_license_api, name='update_api'),
    path('delete', views.delete_license_api, name='delete_api'),
    path('delete-all', views.delete_all_license_api, name='delete_all_api'),
    path('users/create', views.api_create_user, name='api_create_user'),
    path('tiktok/create', views.create_tiktok_license_api, name='create_tiktok_api'),
    path('tiktok/list', views.list_tiktok_license_api, name='list_tiktok_api'),
    path('tiktok/update', views.update_tiktok_license_api, name='update_tiktok_api'),
    path('tiktok/delete', views.delete_tiktok_license_api, name='delete_tiktok_api'),
    path('tiktok/delete-all', views.delete_all_tiktok_license_api, name='delete_all_tiktok_api'),
]

