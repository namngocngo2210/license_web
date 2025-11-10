from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import License


class LicenseCreateForm(forms.Form):
    phone_numbers = forms.CharField(
        label='Danh sách số điện thoại (mỗi dòng 1 số)',
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ví dụ:\\n0912345678\\n0987654321', 'rows': 6}),
        help_text='Tối đa 1000 số. Các số đã tồn tại sẽ được bỏ qua.',
    )
    expires_in = forms.IntegerField(
        min_value=1,
        label='Thời hạn (ngày)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Số ngày'}),
    )

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def _parse_numbers(self):
        raw = self.cleaned_data['phone_numbers']
        numbers = [line.strip() for line in raw.splitlines() if line.strip()]
        if not numbers:
            raise forms.ValidationError('Vui lòng nhập ít nhất 1 số điện thoại.')
        if len(numbers) > 1000:
            raise forms.ValidationError('Tối đa 1000 số điện thoại mỗi lần.')
        return numbers

    def save(self):
        if self.owner is None:
            raise ValueError('Cần có người sở hữu để tạo license.')
        expires_in = self.cleaned_data['expires_in']
        expired_at = timezone.now() + timedelta(days=expires_in)
        created = []
        skipped = []
        for phone_number in self._parse_numbers():
            if License.objects.filter(phone_number=phone_number).exists():
                skipped.append(phone_number)
                continue
            created.append(
                License.objects.create(
                    owner=self.owner,
                    phone_number=phone_number,
                    expired_at=expired_at,
                )
            )
        return created, skipped


class LicenseExtendForm(forms.Form):
    expires_in = forms.IntegerField(
        min_value=1,
        label='Gia hạn thêm (ngày)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Số ngày'}),
    )

    def __init__(self, *args, license_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.license_obj = license_obj

    def save(self):
        if self.license_obj is None:
            raise ValueError('Cần cung cấp license.')
        expires_in = self.cleaned_data['expires_in']
        self.license_obj.expired_at = timezone.now() + timedelta(days=expires_in)
        self.license_obj.save(update_fields=['expired_at', 'updated_at'])
        return self.license_obj

