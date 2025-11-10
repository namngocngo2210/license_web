from django.contrib import admin

from .models import License, UserApiKey


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'code', 'owner', 'expired_at', 'created_at')
    list_filter = ('expired_at', 'created_at')
    search_fields = ('phone_number', 'code', 'owner__username')
    ordering = ('-created_at',)


@admin.register(UserApiKey)
class UserApiKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at', 'last_used_at')
    search_fields = ('user__username', 'key')
    readonly_fields = ('created_at', 'last_used_at')
