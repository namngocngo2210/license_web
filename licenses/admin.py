from django.contrib import admin

from .models import License, UserApiKey, ExtensionPackage, PaymentInfo


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


@admin.register(ExtensionPackage)
class ExtensionPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'days', 'amount', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    list_editable = ('is_active',)


@admin.register(PaymentInfo)
class PaymentInfoAdmin(admin.ModelAdmin):
    list_display = ('account_name', 'account_number', 'bank_name', 'bank_code', 'is_active', 'created_at')
    list_filter = ('is_active', 'bank_code', 'created_at')
    search_fields = ('account_name', 'account_number', 'bank_name', 'bank_code')
    list_editable = ('is_active',)
