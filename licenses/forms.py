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
        is_superuser = self.owner and getattr(self.owner, 'is_superuser', False)
        
        # Non-superuser chỉ được nhập 1 số điện thoại và không cần nhập expires_in
        if not is_superuser:
            self.fields['phone_numbers'].label = 'Số điện thoại'
            self.fields['phone_numbers'].widget = forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập số điện thoại'})
            self.fields['phone_numbers'].help_text = 'Bạn chỉ được tạo 1 license và có hạn trong 1 ngày (dùng demo).'
            # Ẩn trường expires_in cho non-superuser
            self.fields['expires_in'].widget = forms.HiddenInput()
            self.fields['expires_in'].required = False
        
        # Superuser can choose target owner to create licenses for
        if is_superuser:
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
        is_superuser = self.owner and getattr(self.owner, 'is_superuser', False)
        
        # Non-superuser chỉ được nhập 1 số điện thoại
        if not is_superuser:
            phone_number = raw.strip()
            if not phone_number:
                raise forms.ValidationError('Vui lòng nhập số điện thoại.')
            return [phone_number]
        
        # Superuser có thể nhập nhiều số điện thoại
        numbers = [line.strip() for line in raw.splitlines() if line.strip()]
        if not numbers:
            raise forms.ValidationError('Vui lòng nhập ít nhất 1 số điện thoại.')
        if len(numbers) > 1000:
            raise forms.ValidationError('Tối đa 1000 số điện thoại mỗi lần.')
        return numbers

    def save(self):
        if self.owner is None:
            raise ValueError('Cần có người sở hữu để tạo license.')
        
        is_superuser = getattr(self.owner, 'is_superuser', False)
        
        # Non-superuser: set expired_at = 1 ngày
        if not is_superuser:
            expires_in = 1
        else:
            expires_in = self.cleaned_data.get('expires_in', 1)
        
        expired_at = timezone.now() + timedelta(days=expires_in)
        created = []
        skipped = []
        target_owner = self.owner
        
        if is_superuser and 'owner_id' in self.cleaned_data and self.cleaned_data.get('owner_id'):
            User = get_user_model()
            try:
                target_owner = User.objects.get(id=int(self.cleaned_data['owner_id']))
            except (User.DoesNotExist, ValueError, TypeError):
                target_owner = self.owner
        
        # Kiểm tra non-superuser đã có license chưa
        if not is_superuser:
            if License.objects.filter(owner=target_owner).exists():
                raise forms.ValidationError('Bạn chỉ được tạo license 1 lần.')
        
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
    shop_ids = forms.CharField(
        label='Danh sách mã cửa hàng (mỗi dòng 1 mã)',
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ví dụ:\n123456789\n987654321', 'rows': 6}),
        help_text='Tối đa 1000 license. Các license trùng mã cửa hàng sẽ được bỏ qua.',
    )
    expires_in = forms.IntegerField(
        min_value=1,
        label='Thời hạn (ngày)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Số ngày'}),
    )

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        is_superuser = self.owner and getattr(self.owner, 'is_superuser', False)
        
        # Non-superuser chỉ được nhập 1 shop_id và không cần nhập expires_in
        if not is_superuser:
            self.fields['shop_ids'].label = 'Mã cửa hàng'
            self.fields['shop_ids'].widget = forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã cửa hàng'})
            self.fields['shop_ids'].help_text = 'Bạn chỉ được tạo 1 license và có hạn trong 1 ngày.'
            # Ẩn trường expires_in cho non-superuser
            self.fields['expires_in'].widget = forms.HiddenInput()
            self.fields['expires_in'].required = False
        
        # Superuser can choose target owner to create licenses for
        if is_superuser:
            User = get_user_model()
            choices = [(str(u.id), u.username) for u in User.objects.order_by('username').only('id', 'username')]
            self.fields['owner_id'] = forms.ChoiceField(
                choices=choices,
                required=False,
                label='Người dùng',
                widget=forms.Select(attrs={'class': 'form-select'}),
                help_text='Để trống để tạo cho chính bạn.',
            )

    def _parse_shop_ids(self):
        raw = self.cleaned_data['shop_ids']
        is_superuser = self.owner and getattr(self.owner, 'is_superuser', False)
        
        # Non-superuser chỉ được nhập 1 shop_id
        if not is_superuser:
            shop_id = raw.strip()
            if not shop_id:
                raise forms.ValidationError('Vui lòng nhập mã cửa hàng.')
            return [shop_id]
        
        # Superuser có thể nhập nhiều shop_id
        shop_ids = [line.strip() for line in raw.splitlines() if line.strip()]
        if not shop_ids:
            raise forms.ValidationError('Vui lòng nhập ít nhất 1 mã cửa hàng.')
        if len(shop_ids) > 1000:
            raise forms.ValidationError('Tối đa 1000 license mỗi lần.')
        return shop_ids

    def save(self):
        if self.owner is None:
            raise ValueError('Cần có người sở hữu để tạo license.')
        
        is_superuser = getattr(self.owner, 'is_superuser', False)
        
        # Non-superuser: set expired_at = 1 ngày
        if not is_superuser:
            expires_in = 1
        else:
            expires_in = self.cleaned_data.get('expires_in', 1)
        
        expired_at = timezone.now() + timedelta(days=expires_in)
        created = []
        skipped = []
        target_owner = self.owner
        
        if is_superuser and 'owner_id' in self.cleaned_data and self.cleaned_data.get('owner_id'):
            User = get_user_model()
            try:
                target_owner = User.objects.get(id=int(self.cleaned_data['owner_id']))
            except (User.DoesNotExist, ValueError, TypeError):
                target_owner = self.owner
        
        # Kiểm tra non-superuser đã có license chưa
        if not is_superuser:
            if LicenseTikTok.objects.filter(owner=target_owner).exists():
                raise forms.ValidationError('Bạn chỉ được tạo license 1 lần.')
        
        for shop_id in self._parse_shop_ids():
            if LicenseTikTok.objects.filter(shop_id=shop_id, owner=target_owner).exists():
                skipped.append(shop_id)
                continue
            created.append(
                LicenseTikTok.objects.create(
                    owner=target_owner,
                    shop_id=shop_id,
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

