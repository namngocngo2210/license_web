import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


class License(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='licenses',
    )
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    phone_number = models.CharField(max_length=20, unique=True)
    expired_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'license_zalo'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone_number} ({self.code})'

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expired_at


class LicenseTikTok(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tiktok_licenses',
    )
    name = models.CharField(max_length=200, verbose_name='Tên license')
    expired_at = models.DateTimeField(verbose_name='Hết hạn')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'license_tiktok'
        ordering = ['-created_at']
        verbose_name = 'License TikTok'
        verbose_name_plural = 'Licenses TikTok'

    def __str__(self):
        return f'{self.name} ({self.owner.username})'

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expired_at


class UserApiKey(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_key')
    key = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'API Key for {self.user}'

    @staticmethod
    def generate_key() -> str:
        return get_random_string(48)


class ExtensionPackage(models.Model):
    name = models.CharField(max_length=200, verbose_name='Tên gói')
    days = models.PositiveIntegerField(verbose_name='Số ngày')
    amount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Số tiền (VNĐ)')
    is_active = models.BooleanField(default=True, verbose_name='Kích hoạt')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['days']
        verbose_name = 'Gói gia hạn'
        verbose_name_plural = 'Gói gia hạn'

    def __str__(self):
        return f'{self.name} ({self.days} ngày) - {self.amount:,.0f} VNĐ'


class PaymentInfo(models.Model):
    account_name = models.CharField(max_length=200, verbose_name='Tên tài khoản')
    account_number = models.CharField(max_length=50, verbose_name='Số tài khoản')
    bank_code = models.CharField(max_length=20, verbose_name='Mã ngân hàng')
    bank_name = models.CharField(max_length=200, verbose_name='Tên ngân hàng', blank=True)
    note = models.CharField(max_length=500, verbose_name='Ghi chú', blank=True, null=True, help_text='Ghi chú không bắt buộc, có thể để trống')
    is_active = models.BooleanField(default=True, verbose_name='Kích hoạt')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Thông tin chuyển khoản'
        verbose_name_plural = 'Thông tin chuyển khoản'

    def __str__(self):
        return f'{self.account_name} - {self.account_number} ({self.bank_name})'
