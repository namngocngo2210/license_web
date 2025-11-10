from typing import Optional, Tuple

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions

from .models import UserApiKey


class APIKeyAuthentication(BaseAuthentication):
    keyword = 'X-API-Key'

    def authenticate(self, request) -> Optional[Tuple[object, None]]:
        api_key = request.headers.get(self.keyword) or request.query_params.get('api_key')
        if not api_key:
            raise exceptions.AuthenticationFailed('Missing API key')
        try:
            record = UserApiKey.objects.select_related('user').get(key=api_key)
        except UserApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API key')
        # update last used
        UserApiKey.objects.filter(pk=record.pk).update(last_used_at=timezone.now())
        return (record.user, None)

