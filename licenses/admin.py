from django.contrib import admin

from .models import License


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'code', 'owner', 'expired_at', 'created_at')
    list_filter = ('expired_at', 'created_at')
    search_fields = ('phone_number', 'code', 'owner__username')
    ordering = ('-created_at',)
