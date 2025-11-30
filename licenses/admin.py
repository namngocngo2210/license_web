from django.contrib import admin

from .models import License, UserApiKey, ExtensionPackage, PaymentInfo, ExtensionPackageGroup


@admin.register(ExtensionPackageGroup)
class ExtensionPackageGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at')
    search_fields = ('name', 'code')


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
    list_display = ('name', 'group', 'days', 'amount', 'is_active', 'created_at')
    list_filter = ('group', 'is_active', 'created_at')
    search_fields = ('name',)
    list_editable = ('is_active',)


@admin.register(PaymentInfo)
class PaymentInfoAdmin(admin.ModelAdmin):
    list_display = ('account_name', 'account_number', 'bank_name', 'bank_code', 'group', 'is_active', 'created_at')
    list_filter = ('group', 'is_active', 'bank_code', 'created_at')
    search_fields = ('account_name', 'account_number', 'bank_name', 'bank_code')
    list_editable = ('is_active',)
