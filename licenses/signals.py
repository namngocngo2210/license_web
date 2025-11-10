from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import UserApiKey


@receiver(post_save, sender=get_user_model())
def ensure_api_key(sender, instance, created, **kwargs):
    if not instance or not hasattr(instance, 'id'):
        return
    try:
        existing = instance.api_key
        if not existing.key:
            existing.key = UserApiKey.generate_key()
            existing.save(update_fields=['key'])
    except UserApiKey.DoesNotExist:
        UserApiKey.objects.create(user=instance, key=UserApiKey.generate_key(), last_used_at=timezone.now())

