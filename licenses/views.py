import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.http import QueryDict
from urllib.parse import urlencode

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .forms import LicenseCreateForm, LicenseExtendForm, ProfileForm
from .models import License
from .auth import APIKeyAuthentication


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


@login_required
def dashboard(request):
    form = LicenseCreateForm(owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            form = LicenseCreateForm(request.POST, owner=request.user)
            if form.is_valid():
                created, skipped = form.save()
                if created:
                    messages.success(request, f'Đã tạo {len(created)} license.')
                if skipped:
                    messages.warning(request, f'Bỏ qua {len(skipped)} số đã tồn tại.')
                return redirect('licenses:dashboard')
        elif action == 'delete_selected':
            selected_ids = request.POST.getlist('selected_ids')
            
            # Build redirect URL with query parameters preserved
            qs = QueryDict(request.GET.urlencode(), mutable=True)
            redirect_url = f"{reverse('licenses:dashboard')}?{qs.urlencode()}" if qs else reverse('licenses:dashboard')
            
            if not selected_ids:
                messages.warning(request, 'Vui lòng chọn ít nhất một license để xóa.')
                return redirect(redirect_url)

            try:
                selected_ids = [int(pk) for pk in selected_ids]
            except (TypeError, ValueError):
                messages.warning(request, 'Danh sách license không hợp lệ.')
                return redirect(redirect_url)

            # Superuser can delete any license, regular users can only delete their own
            if request.user.is_superuser:
                licenses_qs = License.objects.filter(id__in=selected_ids)
            else:
                licenses_qs = License.objects.filter(owner=request.user, id__in=selected_ids)
            
            deleted_count = licenses_qs.count()
            if deleted_count == 0:
                messages.warning(request, 'Không tìm thấy license tương ứng để xóa.')
            else:
                licenses_qs.delete()
                messages.success(request, f'Đã xóa {deleted_count} license đã chọn.')
            
            return redirect(redirect_url)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    # Base queryset: superuser sees all, others see own licenses only
    if request.user.is_superuser:
        licenses_qs = License.objects.all()
    else:
        licenses_qs = License.objects.filter(owner=request.user)
    licenses_qs = licenses_qs.order_by('-created_at')

    # Filters
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()  # 'active' | 'expired' | ''
    days_min = request.GET.get('days_min', '').strip()
    days_max = request.GET.get('days_max', '').strip()
    user_id = request.GET.get('user_id', '').strip() if request.user.is_superuser else ''

    if q:
        from django.db.models import Q
        licenses_qs = licenses_qs.filter(Q(phone_number__icontains=q) | Q(code__icontains=q))

    now = timezone.now()
    if status_filter == 'active':
        licenses_qs = licenses_qs.filter(expired_at__gt=now)
    elif status_filter == 'expired':
        licenses_qs = licenses_qs.filter(expired_at__lte=now)

    def parse_int(val):
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    dmin = parse_int(days_min)
    dmax = parse_int(days_max)
    if dmin is not None:
        licenses_qs = licenses_qs.filter(expired_at__gte=now + timedelta(days=dmin))
    if dmax is not None:
        licenses_qs = licenses_qs.filter(expired_at__lte=now + timedelta(days=dmax))

    if user_id and request.user.is_superuser:
        try:
            user_id_int = int(user_id)
            licenses_qs = licenses_qs.filter(owner_id=user_id_int)
        except (TypeError, ValueError):
            pass
    page = request.GET.get('page', 1)
    per_page = 10
    paginator = Paginator(licenses_qs, per_page)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Preserve filters in pagination links
    qs_params = {k: v for k, v in request.GET.items() if k != 'page' and v}
    base_querystring = urlencode(qs_params)

    users = []
    if request.user.is_superuser:
        User = get_user_model()
        users = User.objects.order_by('username').values('id', 'username')
    return render(
        request,
        'licenses/dashboard.html',
        {
            'form': _style_form(form),
            'licenses': page_obj.object_list,
            'page_obj': page_obj,
            'is_superuser': request.user.is_superuser,
            'users': users,
            'filters': {'q': q, 'status': status_filter, 'days_min': days_min, 'days_max': days_max, 'user_id': user_id},
            'base_querystring': base_querystring,
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
@authentication_classes([APIKeyAuthentication])
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
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
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
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def list_license_api(request):
    licenses = License.objects.filter(owner=request.user)
    data = [_license_to_dict(license_obj) for license_obj in licenses]
    return Response({'status': True, 'data': data}, status=status.HTTP_200_OK)


@api_view(['PUT'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
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
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
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
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def delete_all_license_api(request):
    deleted_count, _ = License.objects.filter(owner=request.user).delete()
    return Response(
        {'status': True, 'message': 'deleted_all', 'deleted_count': deleted_count},
        status=status.HTTP_200_OK,
    )


@login_required
def profile(request):
    user = request.user
    api_key = getattr(getattr(user, 'api_key', None), 'key', None)
    profile_form = ProfileForm(instance=user)
    password_form = None

    from django.contrib.auth.forms import PasswordChangeForm
    password_form = PasswordChangeForm(user=user, data=None)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            profile_form = ProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Cập nhật thông tin thành công.')
                return redirect('licenses:profile')
        elif action == 'password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, 'Đổi mật khẩu thành công.')
                return redirect('licenses:profile')
            else:
                messages.error(request, 'Không thể đổi mật khẩu. Vui lòng kiểm tra lại.')

    return render(
        request,
        'licenses/profile.html',
        {
            'profile_form': _style_form(profile_form),
            'password_form': _style_form(password_form),
            'api_key': api_key,
        },
    )
