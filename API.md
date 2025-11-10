## Tổng quan API

- Base URL: `https://license.ndk.vn/`
- Xác thực: API Key qua header `X-API-Key: <API_KEY>` (tất cả endpoint yêu cầu API key)
- Content-Type: JSON (trừ khi có ghi chú khác)
- Múi giờ: Asia/Ho_Chi_Minh (GMT+7)

Ghi chú:
- Người dùng thường chỉ quản lý được license của chính mình.
- Superuser xem được tất cả license; các thao tác khác mặc định vẫn theo người dùng đang xác thực trừ khi có quy định riêng.

### Xác thực

Gửi API key trong header:

```
X-API-Key: <API_KEY>
```

Thiếu/sai key sẽ trả về 401/403.

---

### Kiểm tra license
- Method: POST
- Path: `/verify`
- Auth: Bắt buộc (API key)

Request
```json
{
  "code": "a1b2c3d4-...-uuid",
  "phone_number": "0901234567"
}
```

Response 200
```json
{
  "status": true,
  "valid": true,
  "expired_at": 1736428800
}
```

Response 404 (không hợp lệ/không tìm thấy)
```json
{ "status": false, "valid": false, "reason": "not_found" }
```

---

### Tạo license (nhiều số cùng lúc)
- Method: POST
- Path: `/create`
- Auth: Bắt buộc (API key)

Tạo license cho người dùng đang xác thực.

Request
```json
{
  "phone_numbers": ["0901234567", "0902345678"],
  "expires_in": 30
}
```

Response 201
```json
{
  "status": true,
  "data": [
    { "code": "uuid-1", "phone_number": "0901234567", "expired_at": 1736428800, "owner_username": "namnn" },
    { "code": "uuid-2", "phone_number": "0902345678", "expired_at": 1736428800, "owner_username": "namnn" }
  ]
}
```

Lỗi thường gặp
```json
{ "status": false, "error": "phone_numbers phải là mảng không rỗng" }
{ "status": false, "error": "expires_in phải là số nguyên dương" }
```

---

### Lấy danh sách license
- Method: GET
- Path: `/list`
- Auth: Bắt buộc (API key)

Hành vi:
- User thường: trả về license của chính mình.
- Superuser: trả về tất cả license.

Response 200
```json
{
  "status": true,
  "data": [
    { "code": "uuid-1", "phone_number": "0901234567", "expired_at": 1736428800, "owner_username": "user1" },
    { "code": "uuid-2", "phone_number": "0902345678", "expired_at": 1736428800, "owner_username": "user2" }
  ]
}
```

---

### Gia hạn license theo code (nhiều mã)
- Method: PUT
- Path: `/update`
- Auth: Bắt buộc (API key)

Gia hạn các license thuộc người dùng đang xác thực thêm số ngày chỉ định.

Request
```json
{
  "code": ["uuid-1", "uuid-2"],
  "expires_in": 15
}
```

Response 200
```json
{
  "status": true,
  "message": "updated",
  "updated_count": 2,
  "expired_at": 1737602400
}
```

Lỗi thường gặp
```json
{ "status": false, "error": "code là bắt buộc" }
{ "status": false, "error": "expires_in phải là số nguyên dương" }
{ "status": false, "error": "không tìm thấy code nào để cập nhật" }
```

---

### Xóa 1 license theo code
- Method: DELETE
- Path: `/delete`
- Auth: Bắt buộc (API key)

Xóa license theo code của người dùng đang xác thực.

Request
```json
{ "code": "uuid-1" }
```

Response 200
```json
{ "status": true, "message": "deleted" }
```

Lỗi thường gặp
```json
{ "status": false, "error": "code là bắt buộc" }
{ "status": false, "error": "code không tồn tại" }
```

---

### Xóa toàn bộ license của người dùng hiện tại
- Method: DELETE
- Path: `/delete-all`
- Auth: Bắt buộc (API key)

Response 200
```json
{ "status": true, "message": "deleted_all", "deleted_count": 10 }
```

---

### Tạo tài khoản (chỉ superuser)
- Method: POST
- Path: `/users/create`
- Auth: Bắt buộc (API key của superuser)

Request
```json
{
  "username": "newuser",
  "password": "StrongPass123",
  "email": "user@example.com",
  "first_name": "New",
  "last_name": "User"
}
```

Response 201
```json
{
  "status": true,
  "message": "user_created",
  "user": {
    "id": 12,
    "username": "newuser",
    "email": "user@example.com",
    "first_name": "New",
    "last_name": "User",
    "is_superuser": false
  },
  "api_key": "generated-api-key-if-available"
}
```

Lỗi thường gặp
```json
{ "status": false, "error": "Forbidden" }             // không phải superuser
{ "status": false, "error": "username và password là bắt buộc" }
{ "status": false, "error": "username đã tồn tại" }
```

---

### Ví dụ cURL

Verify
```bash
curl -X POST https://license.ndk.vn/verify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d '{"code":"uuid-1","phone_number":"0901234567"}'
```

List
```bash
curl -H "X-API-Key: <API_KEY>" https://license.ndk.vn/list
```

Tạo user (cần API key của superuser)
```bash
curl -X POST https://license.ndk.vn/users/create \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <SUPERUSER_API_KEY>" \
  -d '{"username":"newuser","password":"StrongPass123"}'
```


