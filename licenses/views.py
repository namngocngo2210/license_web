import uuid

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication

from .forms import LicenseCreateForm, LicenseExtendForm
from .models import License


def _style_form(form):
    for field in form.fields.values():
        css_class = field.widget.attrs.get('class', '')
        if 'form-control' not in css_class:
            field.widget.attrs['class'] = f'{css_class} form-control'.strip()
    return form


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form(self)


class StyledLoginView(LoginView):
    form_class = StyledAuthenticationForm
    template_name = 'registration/login.html'


def register(request):
    if request.user.is_authenticated:
        return redirect('licenses:dashboard')

    if request.method == 'POST':
        form = _style_form(UserCreationForm(request.POST))
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Tạo tài khoản thành công.')
            return redirect('licenses:dashboard')
    else:
        form = _style_form(UserCreationForm())

    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    if request.method == 'POST':
        form = LicenseCreateForm(request.POST, owner=request.user)
        if form.is_valid():
            created, skipped = form.save()
            if created:
                messages.success(request, f'Đã tạo {len(created)} license.')
            if skipped:
                messages.warning(request, f'Bỏ qua {len(skipped)} số đã tồn tại.')
            return redirect('licenses:dashboard')
    else:
        form = LicenseCreateForm(owner=request.user)

    licenses = License.objects.filter(owner=request.user)
    return render(
        request,
        'licenses/dashboard.html',
        {
            'form': _style_form(form),
            'licenses': licenses,
        },
    )


@login_required
def extend_license(request, pk):
    license_obj = get_object_or_404(License, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = LicenseExtendForm(request.POST, license_obj=license_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Gia hạn license thành công.')
            return redirect('licenses:dashboard')
    else:
        form = LicenseExtendForm()

    return render(
        request,
        'licenses/license_extend.html',
        {
            'form': _style_form(form),
            'license': license_obj,
        },
    )


@login_required
def delete_license(request, pk):
    license_obj = get_object_or_404(License, pk=pk, owner=request.user)

    if request.method == 'POST':
        phone_number = license_obj.phone_number
        license_obj.delete()
        messages.success(request, f'Đã xóa license cho {phone_number}.')
        return redirect('licenses:dashboard')

    return render(
        request,
        'licenses/license_confirm_delete.html',
        {'license': license_obj},
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_license(request):
    code = request.data.get('code')
    phone_number = request.data.get('phone_number')

    if not code:
        return Response(
            {'status': False, 'error': 'code là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not phone_number:
        return Response(
            {'status': False, 'error': 'phone_number là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        normalized_code = str(uuid.UUID(str(code)))
    except (ValueError, AttributeError, TypeError):
        return Response(
            {'status': False, 'valid': False, 'reason': 'not_found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        license_obj = License.objects.get(code=normalized_code, phone_number=phone_number)
    except License.DoesNotExist:
        return Response(
            {'status': False, 'valid': False, 'reason': 'not_found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        expired_at_ts = int(license_obj.expired_at.timestamp())
    except (OverflowError, OSError, ValueError, AttributeError):
        return Response(
            {'status': False, 'valid': False, 'reason': 'invalid_expired_at'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if license_obj.is_expired:
        return Response(
            {
                'status': True,
                'valid': False,
                'expired_at': expired_at_ts,
            },
            status=status.HTTP_410_GONE,
        )

    return Response(
        {
            'status': True,
            'valid': True,
            'expired_at': expired_at_ts,
        },
        status=status.HTTP_200_OK,
    )


def _license_to_dict(license_obj):
    return {
        'code': str(license_obj.code),
        'phone_number': license_obj.phone_number,
        'expired_at': int(license_obj.expired_at.timestamp()),
    }


@api_view(['POST'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def create_license_api(request):
    phone_numbers = request.data.get('phone_numbers')
    expires_in = request.data.get('expires_in')

    if not isinstance(phone_numbers, list) or not phone_numbers:
        return Response(
            {'status': False, 'error': 'phone_numbers phải là mảng không rỗng'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        expires_in = int(expires_in)
        if expires_in <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {'status': False, 'error': 'expires_in phải là số nguyên dương'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(phone_numbers) > 1000:
        return Response(
            {'status': False, 'error': 'phone_numbers vượt quá 1000 số'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expires_at = timezone.now() + timedelta(days=expires_in)
    created = []

    for phone in phone_numbers:
        if not isinstance(phone, str) or not phone.strip():
            return Response(
                {'status': False, 'error': 'Có số điện thoại không hợp lệ'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        phone = phone.strip()
        if License.objects.filter(phone_number=phone).exists():
            continue
        created.append(
            License.objects.create(
                owner=request.user,
                phone_number=phone,
                expired_at=expires_at,
            )
        )

    data = [_license_to_dict(item) for item in created]
    return Response({'status': True, 'data': data}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def list_license_api(request):
    licenses = License.objects.filter(owner=request.user)
    data = [_license_to_dict(license_obj) for license_obj in licenses]
    return Response({'status': True, 'data': data}, status=status.HTTP_200_OK)


@api_view(['PUT'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def update_license_api(request):
    codes = request.data.get('code')
    expires_in = request.data.get('expires_in')

    if codes is None:
        return Response(
            {'status': False, 'error': 'code là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        expires_in = int(expires_in)
        if expires_in <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {'status': False, 'error': 'expires_in phải là số nguyên dương'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(codes, str):
        codes = [codes]
    elif isinstance(codes, list):
        if not codes:
            return Response(
                {'status': False, 'error': 'code phải là string hoặc array không rỗng'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        return Response(
            {'status': False, 'error': 'code phải là string hoặc array'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    updated = 0
    not_found = []
    expired_at = timezone.now() + timedelta(days=expires_in)

    for code in codes:
        try:
            license_obj = License.objects.get(code=code, owner=request.user)
            license_obj.expired_at = expired_at
            license_obj.save(update_fields=['expired_at', 'updated_at'])
            updated += 1
        except License.DoesNotExist:
            not_found.append(code)

    if updated == 0:
        return Response(
            {'status': False, 'error': 'không tìm thấy code nào để cập nhật'},
            status=status.HTTP_404_NOT_FOUND,
        )

    response_data = {
        'status': True,
        'message': 'updated',
        'updated_count': updated,
        'expired_at': int(expired_at.timestamp()),
    }

    if not_found:
        response_data['not_found_codes'] = not_found

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def delete_license_api(request):
    code = request.data.get('code')
    if not code:
        return Response(
            {'status': False, 'error': 'code là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        license_obj = License.objects.get(code=code, owner=request.user)
    except License.DoesNotExist:
        return Response(
            {'status': False, 'error': 'code không tồn tại'},
            status=status.HTTP_404_NOT_FOUND,
        )

    license_obj.delete()
    return Response({'status': True, 'message': 'deleted'}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def delete_all_license_api(request):
    deleted_count, _ = License.objects.filter(owner=request.user).delete()
    return Response(
        {'status': True, 'message': 'deleted_all', 'deleted_count': deleted_count},
        status=status.HTTP_200_OK,
    )
