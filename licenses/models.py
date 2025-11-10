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
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone_number} ({self.code})'

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
