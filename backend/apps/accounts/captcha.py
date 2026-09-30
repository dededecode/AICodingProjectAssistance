"""登录图形验证码：生成（Pillow 画图）与一次性校验。

JWT 无 session，验证码存入 LoginCaptcha 表；5 分钟内有效、一次性消耗。
"""
import base64
import io
import random
from datetime import timedelta

from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from .models import LoginCaptcha

# 去易混淆字符（无 0/O/1/I）
_CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CAPTCHA_LEN = 4
_VALID_SECONDS = 5 * 60
MAX_FAILS = 3


def _cleanup():
    LoginCaptcha.objects.filter(expires_at__lt=timezone.now()).delete()


def generate_captcha():
    """生成一条验证码记录并返回 captcha_id + base64 图片。"""
    _cleanup()
    code = "".join(random.choices(_CAPTCHA_CHARS, k=_CAPTCHA_LEN))
    cap = LoginCaptcha.objects.create(
        code=code, expires_at=timezone.now() + timedelta(seconds=_VALID_SECONDS)
    )
    return {"captcha_id": cap.id, "image": _render_image(code)}


def _render_image(code):
    width, height = 130, 44
    bg = (random.randint(230, 255), random.randint(230, 255), random.randint(230, 255))
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    # 干扰线
    for _ in range(4):
        draw.line(
            [
                (random.randint(0, width), random.randint(0, height)),
                (random.randint(0, width), random.randint(0, height)),
            ],
            fill=(random.randint(0, 180), random.randint(0, 180), random.randint(0, 180)),
            width=1,
        )
    # 字符（每字符随机颜色/微位移/轻微旋转）
    for i, ch in enumerate(code):
        try:
            font = ImageFont.load_default(size=30)
        except TypeError:  # 旧版 Pillow 不支持 size 参数
            font = ImageFont.load_default()
        color = (random.randint(0, 110), random.randint(0, 110), random.randint(0, 110))
        x = 12 + i * 28 + random.randint(-3, 3)
        y = random.randint(2, 8)
        draw.text((x, y), ch, font=font, fill=color)
    # 噪点
    for _ in range(80):
        draw.point(
            (random.randint(0, width - 1), random.randint(0, height - 1)),
            fill=(random.randint(0, 150),) * 3,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def verify_captcha(captcha_id, code):
    """校验验证码。

    成功即标记 used（一次性）；失败累计 fail_count，同一张最多允许重试
    MAX_FAILS 次，超过后作废，防止对固定验证码暴力尝试。
    """
    if not captcha_id or not code:
        return False
    try:
        cap = LoginCaptcha.objects.get(id=captcha_id)
    except (LoginCaptcha.DoesNotExist, ValueError, TypeError):
        return False
    if cap.used or cap.expires_at < timezone.now():
        return False
    if code.strip().upper() != cap.code:
        cap.fail_count += 1
        if cap.fail_count >= MAX_FAILS:
            cap.used = True
        cap.save(update_fields=["fail_count", "used"])
        return False
    cap.used = True
    cap.save(update_fields=["used"])
    return True
