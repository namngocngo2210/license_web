from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import License, LicenseTikTok
from django.contrib.auth import get_user_model


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
        # Superuser can choose target owner to create licenses for
        if self.owner and getattr(self.owner, 'is_superuser', False):
            User = get_user_model()
            choices = [(str(u.id), u.username) for u in User.objects.order_by('username').only('id', 'username')]
            self.fields['owner_id'] = forms.ChoiceField(
                choices=choices,
                required=False,
                label='Người dùng',
                widget=forms.Select(attrs={'class': 'form-select'}),
                help_text='Để trống để tạo cho chính bạn.',
            )

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
        target_owner = self.owner
        if getattr(self.owner, 'is_superuser', False) and 'owner_id' in self.cleaned_data and self.cleaned_data.get('owner_id'):
            User = get_user_model()
            try:
                target_owner = User.objects.get(id=int(self.cleaned_data['owner_id']))
            except (User.DoesNotExist, ValueError, TypeError):
                target_owner = self.owner
        for phone_number in self._parse_numbers():
            if License.objects.filter(phone_number=phone_number).exists():
                skipped.append(phone_number)
                continue
            created.append(
                License.objects.create(
                    owner=target_owner,
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


class ProfileForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
        }


class LicenseTikTokCreateForm(forms.Form):
    names = forms.CharField(
        label='Danh sách tên license (mỗi dòng 1 tên)',
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ví dụ:\nLicense 1\nLicense 2', 'rows': 6}),
        help_text='Tối đa 1000 license. Các license trùng tên sẽ được bỏ qua.',
    )
    expires_in = forms.IntegerField(
        min_value=1,
        label='Thời hạn (ngày)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Số ngày'}),
    )

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        # Superuser can choose target owner to create licenses for
        if self.owner and getattr(self.owner, 'is_superuser', False):
            User = get_user_model()
            choices = [(str(u.id), u.username) for u in User.objects.order_by('username').only('id', 'username')]
            self.fields['owner_id'] = forms.ChoiceField(
                choices=choices,
                required=False,
                label='Người dùng',
                widget=forms.Select(attrs={'class': 'form-select'}),
                help_text='Để trống để tạo cho chính bạn.',
            )

    def _parse_names(self):
        raw = self.cleaned_data['names']
        names = [line.strip() for line in raw.splitlines() if line.strip()]
        if not names:
            raise forms.ValidationError('Vui lòng nhập ít nhất 1 tên license.')
        if len(names) > 1000:
            raise forms.ValidationError('Tối đa 1000 license mỗi lần.')
        return names

    def save(self):
        if self.owner is None:
            raise ValueError('Cần có người sở hữu để tạo license.')
        expires_in = self.cleaned_data['expires_in']
        expired_at = timezone.now() + timedelta(days=expires_in)
        created = []
        skipped = []
        target_owner = self.owner
        if getattr(self.owner, 'is_superuser', False) and 'owner_id' in self.cleaned_data and self.cleaned_data.get('owner_id'):
            User = get_user_model()
            try:
                target_owner = User.objects.get(id=int(self.cleaned_data['owner_id']))
            except (User.DoesNotExist, ValueError, TypeError):
                target_owner = self.owner
        for name in self._parse_names():
            if LicenseTikTok.objects.filter(name=name, owner=target_owner).exists():
                skipped.append(name)
                continue
            created.append(
                LicenseTikTok.objects.create(
                    owner=target_owner,
                    name=name,
                    expired_at=expired_at,
                )
            )
        return created, skipped


class LicenseTikTokExtendForm(forms.Form):
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

