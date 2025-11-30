import uuid
import json
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.http import QueryDict, JsonResponse, HttpResponse
from django.conf import settings
from django import forms
from urllib.parse import urlencode

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .forms import LicenseCreateForm, LicenseExtendForm, ProfileForm, LicenseTikTokCreateForm, LicenseTikTokExtendForm
from .models import License, LicenseTikTok, ExtensionPackage, PaymentInfo
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
            # Logic kiểm tra giới hạn license đã được gỡ bỏ

            
            form = LicenseCreateForm(request.POST, owner=request.user)
            if form.is_valid():
                try:
                    created, skipped = form.save()
                    if created:
                        messages.success(request, f'Đã tạo {len(created)} license.')
                    if skipped:
                        messages.warning(request, f'Bỏ qua {len(skipped)} số đã tồn tại.')
                    return redirect('licenses:dashboard')
                except forms.ValidationError as e:
                    form.add_error(None, e)
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
    
    # Non-superuser bây giờ có thể tạo nhiều license
    can_create_license = True
    
    # Load banks data for payment info
    banks_data = []
    try:
        banks_file = Path(settings.BASE_DIR) / 'banks.json'
        with open(banks_file, 'r', encoding='utf-8') as f:
            banks_data = json.load(f)
    except FileNotFoundError:
        pass
    
    return render(
        request,
        'licenses/dashboard.html',
        {
            'form': _style_form(form),
            'licenses': page_obj.object_list,
            'page_obj': page_obj,
            'is_superuser': request.user.is_superuser,
            'users': users,
            'can_create_license': can_create_license,
            'filters': {'q': q, 'status': status_filter, 'days_min': days_min, 'days_max': days_max, 'user_id': user_id},
            'base_querystring': base_querystring,
            'banks_data': json.dumps(banks_data),
        },
    )


@login_required
def extend_license(request, pk):
    if request.user.is_superuser:
        license_obj = get_object_or_404(License, pk=pk)
    else:
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
    if request.user.is_superuser:
        license_obj = get_object_or_404(License, pk=pk)
    else:
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
        'owner_username': getattr(license_obj.owner, 'username', None),
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
    if request.user.is_superuser:
        licenses = License.objects.all()
    else:
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
    now = timezone.now()
    expired_at_list = []

    for code in codes:
        try:
            license_obj = License.objects.get(code=code, owner=request.user)
            # Gia hạn thêm số ngày: nếu chưa hết hạn thì cộng vào ngày hết hạn hiện tại, nếu đã hết hạn thì từ bây giờ
            if license_obj.expired_at > now:
                # Chưa hết hạn: cộng thêm vào ngày hết hạn hiện tại
                license_obj.expired_at = license_obj.expired_at + timedelta(days=expires_in)
            else:
                # Đã hết hạn: tính từ bây giờ
                license_obj.expired_at = now + timedelta(days=expires_in)
            license_obj.save(update_fields=['expired_at', 'updated_at'])
            expired_at_list.append(int(license_obj.expired_at.timestamp()))
            updated += 1
        except License.DoesNotExist:
            not_found.append(code)

    if updated == 0:
        return Response(
            {'status': False, 'error': 'không tìm thấy code nào để cập nhật'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Lấy expired_at của license đầu tiên được cập nhật (hoặc có thể lấy max/min tùy logic)
    expired_at = expired_at_list[0] if expired_at_list else int((now + timedelta(days=expires_in)).timestamp())

    response_data = {
        'status': True,
        'message': 'updated',
        'updated_count': updated,
        'expired_at': expired_at,
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


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def api_create_user(request):
    # Allow only superusers via API key
    user = request.user
    if not user or not user.is_authenticated or not user.is_superuser:
        return Response({'status': False, 'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip()
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()

    if not username or not password:
        return Response(
            {'status': False, 'error': 'username và password là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    User = get_user_model()
    if User.objects.filter(username=username).exists():
        return Response(
            {'status': False, 'error': 'username đã tồn tại'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_user = User.objects.create_user(
        username=username,
        password=password,
        email=email or None,
        first_name=first_name,
        last_name=last_name,
    )

    # Fetch API key if created by signal
    api_key_value = None
    try:
        api_key_value = getattr(getattr(new_user, 'api_key', None), 'key', None)
    except Exception:
        api_key_value = None

    return Response(
        {
            'status': True,
            'message': 'user_created',
            'user': {
                'id': new_user.id,
                'username': new_user.username,
                'email': new_user.email,
                'first_name': new_user.first_name,
                'last_name': new_user.last_name,
                'is_superuser': new_user.is_superuser,
            },
            'api_key': api_key_value,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def verify_tiktok_license(request):
    code = request.data.get('code')
    shop_id = request.data.get('shop_id')

    if not code:
        return Response(
            {'status': False, 'error': 'code là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not shop_id:
        return Response(
            {'status': False, 'error': 'shop_id là bắt buộc'},
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
        license_obj = LicenseTikTok.objects.get(code=normalized_code, shop_id=shop_id)
    except LicenseTikTok.DoesNotExist:
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


def _tiktok_license_to_dict(license_obj):
    return {
        'id': license_obj.id,
        'code': str(license_obj.code),
        'shop_id': license_obj.shop_id,
        'expired_at': int(license_obj.expired_at.timestamp()),
        'created_at': int(license_obj.created_at.timestamp()),
        'updated_at': int(license_obj.updated_at.timestamp()),
        'owner_username': getattr(license_obj.owner, 'username', None),
    }


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def create_tiktok_license_api(request):
    shop_ids = request.data.get('shop_ids')
    expires_in = request.data.get('expires_in')

    if not isinstance(shop_ids, list) or not shop_ids:
        return Response(
            {'status': False, 'error': 'shop_ids phải là mảng không rỗng'},
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

    if len(shop_ids) > 1000:
        return Response(
            {'status': False, 'error': 'shop_ids vượt quá 1000 license'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expired_at = timezone.now() + timedelta(days=expires_in)
    created = []

    for shop_id in shop_ids:
        if not isinstance(shop_id, str) or not shop_id.strip():
            return Response(
                {'status': False, 'error': 'Có mã cửa hàng không hợp lệ'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        shop_id = shop_id.strip()
        if LicenseTikTok.objects.filter(shop_id=shop_id, owner=request.user).exists():
            continue
        created.append(
            LicenseTikTok.objects.create(
                owner=request.user,
                shop_id=shop_id,
                expired_at=expired_at,
            )
        )

    data = [_tiktok_license_to_dict(item) for item in created]
    return Response({'status': True, 'data': data}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def list_tiktok_license_api(request):
    if request.user.is_superuser:
        licenses = LicenseTikTok.objects.all()
    else:
        licenses = LicenseTikTok.objects.filter(owner=request.user)
    data = [_tiktok_license_to_dict(license_obj) for license_obj in licenses]
    return Response({'status': True, 'data': data}, status=status.HTTP_200_OK)


@api_view(['PUT'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def update_tiktok_license_api(request):
    id = request.data.get('id')
    shop_id = request.data.get('shop_id')

    if not id:
        return Response(
            {'status': False, 'error': 'id là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not shop_id or not isinstance(shop_id, str) or not shop_id.strip():
        return Response(
            {'status': False, 'error': 'shop_id là bắt buộc và phải là chuỗi không rỗng'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    shop_id = shop_id.strip()

    try:
        license_obj = LicenseTikTok.objects.get(id=id, owner=request.user)
    except LicenseTikTok.DoesNotExist:
        return Response(
            {'status': False, 'error': 'license không tồn tại'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Kiểm tra mã cửa hàng trùng (trừ chính nó)
    if LicenseTikTok.objects.filter(shop_id=shop_id, owner=request.user).exclude(id=id).exists():
        return Response(
            {'status': False, 'error': 'Mã cửa hàng đã tồn tại'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    license_obj.shop_id = shop_id
    license_obj.save(update_fields=['shop_id', 'updated_at'])

    return Response(
        {
            'status': True,
            'message': 'updated',
            'data': _tiktok_license_to_dict(license_obj),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def delete_tiktok_license_api(request):
    id = request.data.get('id')
    if not id:
        return Response(
            {'status': False, 'error': 'id là bắt buộc'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        license_obj = LicenseTikTok.objects.get(id=id, owner=request.user)
    except LicenseTikTok.DoesNotExist:
        return Response(
            {'status': False, 'error': 'license không tồn tại'},
            status=status.HTTP_404_NOT_FOUND,
        )

    license_obj.delete()
    return Response({'status': True, 'message': 'deleted'}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([APIKeyAuthentication])
@permission_classes([AllowAny])
def delete_all_tiktok_license_api(request):
    deleted_count, _ = LicenseTikTok.objects.filter(owner=request.user).delete()
    return Response(
        {'status': True, 'message': 'deleted_all', 'deleted_count': deleted_count},
        status=status.HTTP_200_OK,
    )


@login_required
def dashboard_tiktok(request):
    form = LicenseTikTokCreateForm(owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            # Kiểm tra nếu non-superuser đã có license thì không cho tạo
            if not request.user.is_superuser:
                if LicenseTikTok.objects.filter(owner=request.user).exists():
                    messages.error(request, 'Bạn chỉ được tạo license 1 lần.')
                    return redirect('licenses:dashboard_tiktok')
            
            form = LicenseTikTokCreateForm(request.POST, owner=request.user)
            if form.is_valid():
                try:
                    created, skipped = form.save()
                    if created:
                        messages.success(request, f'Đã tạo {len(created)} license TikTok.')
                    if skipped:
                        messages.warning(request, f'Bỏ qua {len(skipped)} license đã tồn tại.')
                    return redirect('licenses:dashboard_tiktok')
                except forms.ValidationError as e:
                    form.add_error(None, e)
        elif action == 'delete_selected':
            selected_ids = request.POST.getlist('selected_ids')
            
            # Build redirect URL with query parameters preserved
            qs = QueryDict(request.GET.urlencode(), mutable=True)
            redirect_url = f"{reverse('licenses:dashboard_tiktok')}?{qs.urlencode()}" if qs else reverse('licenses:dashboard_tiktok')
            
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
                licenses_qs = LicenseTikTok.objects.filter(id__in=selected_ids)
            else:
                licenses_qs = LicenseTikTok.objects.filter(owner=request.user, id__in=selected_ids)
            
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
        licenses_qs = LicenseTikTok.objects.all()
    else:
        licenses_qs = LicenseTikTok.objects.filter(owner=request.user)
    licenses_qs = licenses_qs.order_by('-created_at')

    # Filters
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()  # 'active' | 'expired' | ''
    days_min = request.GET.get('days_min', '').strip()
    days_max = request.GET.get('days_max', '').strip()
    user_id = request.GET.get('user_id', '').strip() if request.user.is_superuser else ''

    if q:
        from django.db.models import Q
        licenses_qs = licenses_qs.filter(Q(shop_id__icontains=q) | Q(code__icontains=q) | Q(owner__username__icontains=q))

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
    
    # Kiểm tra non-superuser có thể tạo license không (chưa có license nào)
    can_create_license = request.user.is_superuser or not LicenseTikTok.objects.filter(owner=request.user).exists()
    
    # Load banks data for payment info
    banks_data = []
    try:
        banks_file = Path(settings.BASE_DIR) / 'banks.json'
        with open(banks_file, 'r', encoding='utf-8') as f:
            banks_data = json.load(f)
    except FileNotFoundError:
        pass
    
    return render(
        request,
        'licenses/dashboard_tiktok.html',
        {
            'form': _style_form(form),
            'licenses': page_obj.object_list,
            'page_obj': page_obj,
            'is_superuser': request.user.is_superuser,
            'users': users,
            'can_create_license': can_create_license,
            'filters': {'q': q, 'status': status_filter, 'days_min': days_min, 'days_max': days_max, 'user_id': user_id},
            'base_querystring': base_querystring,
            'banks_data': json.dumps(banks_data),
        },
    )


@login_required
def extend_tiktok_license(request, pk):
    if request.user.is_superuser:
        license_obj = get_object_or_404(LicenseTikTok, pk=pk)
    else:
        license_obj = get_object_or_404(LicenseTikTok, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = LicenseTikTokExtendForm(request.POST, license_obj=license_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Gia hạn license TikTok thành công.')
            return redirect('licenses:dashboard_tiktok')
    else:
        form = LicenseTikTokExtendForm()

    return render(
        request,
        'licenses/license_extend.html',
        {
            'form': _style_form(form),
            'license': license_obj,
        },
    )


@login_required
def delete_tiktok_license(request, pk):
    if request.user.is_superuser:
        license_obj = get_object_or_404(LicenseTikTok, pk=pk)
    else:
        license_obj = get_object_or_404(LicenseTikTok, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        shop_id = license_obj.shop_id
        license_obj.delete()
        messages.success(request, f'Đã xóa license TikTok "{shop_id}".')
        
        # Preserve query parameters when redirecting
        qs = QueryDict(request.GET.urlencode(), mutable=True)
        redirect_url = f"{reverse('licenses:dashboard_tiktok')}?{qs.urlencode()}" if qs else reverse('licenses:dashboard_tiktok')
        return redirect(redirect_url)
    
    # Redirect back to dashboard with query params if GET request
    # The modal in dashboard will handle the confirmation
    qs = QueryDict(request.GET.urlencode(), mutable=True)
    redirect_url = f"{reverse('licenses:dashboard_tiktok')}?{qs.urlencode()}" if qs else reverse('licenses:dashboard_tiktok')
    return redirect(redirect_url)


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


@login_required
def get_extension_packages(request):
    """API endpoint để lấy danh sách gói gia hạn"""
    packages = ExtensionPackage.objects.filter(is_active=True).order_by('days')
    data = [{'id': p.id, 'name': p.name, 'days': p.days, 'amount': float(p.amount)} for p in packages]
    return JsonResponse({'packages': data})


@login_required
def get_payment_info(request):
    """API endpoint để lấy thông tin chuyển khoản"""
    payment = PaymentInfo.objects.filter(is_active=True).first()
    if not payment:
        return JsonResponse({'error': 'Không có thông tin chuyển khoản'}, status=404)
    
    data = {
        'id': payment.id,
        'account_name': payment.account_name,
        'account_number': payment.account_number,
        'bank_code': payment.bank_code,
        'bank_name': payment.bank_name,
        'note': payment.note or '',
    }
    return JsonResponse(data)


@login_required
def generate_qr_code(request):
    """Tạo URL QR code từ thông tin chuyển khoản sử dụng VietQR"""
    payment_id = request.GET.get('payment_id')
    package_id = request.GET.get('package_id')
    license_id = request.GET.get('license_id')
    license_type = request.GET.get('license_type', 'zalo')  # Default to 'zalo' for backward compatibility
    
    if not payment_id or not package_id or not license_id:
        return JsonResponse({'error': 'Thiếu thông tin'}, status=400)
    
    try:
        payment = PaymentInfo.objects.get(id=payment_id, is_active=True)
        package = ExtensionPackage.objects.get(id=package_id, is_active=True)
        
        # Get license object based on type
        if license_type == 'tiktok':
            license_obj = LicenseTikTok.objects.get(id=license_id)
        else:
            license_obj = License.objects.get(id=license_id)
        
        if not request.user.is_superuser and license_obj.owner != request.user:
            return JsonResponse({'error': 'Không có quyền'}, status=403)
    except (PaymentInfo.DoesNotExist, ExtensionPackage.DoesNotExist, License.DoesNotExist, LicenseTikTok.DoesNotExist):
        return JsonResponse({'error': 'Không tìm thấy thông tin'}, status=404)
    
    # Lấy số tiền từ package
    amount = int(package.amount) if package.amount else 0
    
    # Tạo nội dung ghi chú (nếu có) với thông tin license
    note = payment.note or ''
    if note and '{' in note:
        # Format note với thông tin license nếu có placeholder
        try:
            if license_type == 'tiktok':
                note = note.format(
                    license_code=str(license_obj.code),
                    shop_id=license_obj.shop_id,
                    package_name=package.name,
                    days=package.days
                )
            else:
                note = note.format(
                    license_code=str(license_obj.code),
                    phone_number=license_obj.phone_number,
                    package_name=package.name,
                    days=package.days
                )
        except (KeyError, ValueError):
            # Nếu format lỗi, giữ nguyên note gốc
            pass
    
    # Tạo nội dung chuyển khoản
    transfer_content_parts = []
    if note:
        transfer_content_parts.append(note)
    if license_type == 'tiktok':
        transfer_content_parts.append('ltt')
    else:
        transfer_content_parts.append('lzl')
    transfer_content_parts.append(str(package.days))  # Số ngày theo gói
    if license_type == 'tiktok':
        transfer_content_parts.append(str(license_obj.shop_id))  # Shop ID cho TikTok
    else:
        transfer_content_parts.append(license_obj.phone_number)  # Số điện thoại cho Zalo
    transfer_content = ' '.join(transfer_content_parts)  # Nối bằng khoảng trắng
    
    # Tạo URL QR code theo định dạng VietQR
    # Format: https://img.vietqr.io/image/${bankcode}-${accountno}-compact.jpg?amount=${money}&addInfo=${memo}&accountName=${accountname}
    qr_url = (
        f"https://img.vietqr.io/image/{payment.bank_code}-{payment.account_number}-compact.jpg"
        f"?amount={quote(str(amount))}"
        f"&addInfo={quote(transfer_content)}"
        f"&accountName={quote(payment.account_name)}"
    )
    
    license_data = {
        'code': str(license_obj.code),
    }
    if license_type == 'tiktok':
        license_data['shop_id'] = license_obj.shop_id
    else:
        license_data['phone_number'] = license_obj.phone_number
    
    return JsonResponse({
        'qr_code': qr_url,
        'payment_info': {
            'account_name': payment.account_name,
            'account_number': payment.account_number,
            'bank_name': payment.bank_name,
            'bank_code': payment.bank_code,
            'note': note,
            'transfer_content': transfer_content,
        },
        'package': {
            'name': package.name,
            'days': package.days,
            'amount': float(package.amount),
        },
        'license': license_data,
    })
