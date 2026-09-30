from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ROLE_CHOICES, User


def _normalize_superuser_role(data, instance):
    """超管统一按 admin 输出。

    `manage.py createsuperuser` 只设置 is_superuser，不会设置 role，账号的 role 仍是模型
    默认值 developer（但没有任何权限组）。后端各处（rbac/api_map.py 等）都把
    「is_superuser 或 role == admin」当管理员放行，若这里原样下发 developer，
    前端就会把超管当成无权限的普通开发——菜单只剩「首页」、角色标签显示「开发」、
    项目详情里也不显示管理按钮。
    """
    if instance.is_superuser:
        data["role"] = "admin"
    return data


class UserSerializer(serializers.ModelSerializer):
    """当前登录用户信息（登录返回体 + /api/auth/me/）。只读。"""

    role = serializers.ChoiceField(choices=ROLE_CHOICES)
    # 前端 frontend/src/rbac.js 的 hasPerm 判定为「role === 'admin' || is_superuser」，
    # 因此 is_superuser 必须随用户信息下发，否则超管拿不到任何菜单。
    is_superuser = serializers.BooleanField(read_only=True)
    groups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "name", "capability", "email", "role", "is_superuser", "first_name", "last_name", "groups"]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        return _normalize_superuser_role(super().to_representation(instance), instance)


class UserManageSerializer(serializers.ModelSerializer):
    """管理员用户管理序列化器。"""
    role = serializers.ChoiceField(choices=ROLE_CHOICES)
    password = serializers.CharField(write_only=True, required=False, min_length=6, allow_blank=True)
    mcp_token = serializers.CharField(read_only=True)
    # 只读：超管是系统账号，不允许通过接口把别的账号提权为超管
    is_superuser = serializers.BooleanField(read_only=True)
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=Group.objects.all(), required=False)

    class Meta:
        model = User
        fields = ["id", "username", "name", "capability", "email", "role", "is_superuser", "is_active", "first_name", "last_name", "password", "mcp_token", "groups"]
        read_only_fields = ["id", "mcp_token"]

    def to_representation(self, instance):
        # 与 UserSerializer 保持一致：超管角色统一显示为管理员
        return _normalize_superuser_role(super().to_representation(instance), instance)

    def create(self, validated_data):
        groups = validated_data.pop("groups", None)
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        if groups is not None:
            user.groups.set(groups)
        return user

    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if groups is not None:
            instance.groups.set(groups)
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("原密码错误")
        return value


class LoginSerializer(serializers.Serializer):
    """登录：encrypted 为 RSA 密文（含 username/password/captcha_id/captcha_code），
    解密后校验图形验证码，返回 access/refresh token + 用户信息。"""

    encrypted = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from .captcha import verify_captcha
        from .rsa_crypto import decrypt_payload

        try:
            data = decrypt_payload(attrs["encrypted"])
        except ValueError as e:
            raise serializers.ValidationError(str(e))

        if not verify_captcha(data.get("captcha_id"), data.get("captcha_code")):
            raise serializers.ValidationError("验证码错误或已过期，请刷新后重试")

        from django.contrib.auth import authenticate

        user = authenticate(username=data.get("username") or "", password=data.get("password") or "")
        if not user:
            raise serializers.ValidationError("用户名或密码错误")
        if not user.is_active:
            raise serializers.ValidationError("账号已禁用")

        refresh = RefreshToken.for_user(user)
        attrs["user"] = user
        attrs["refresh"] = str(refresh)
        attrs["access"] = str(refresh.access_token)
        return attrs
