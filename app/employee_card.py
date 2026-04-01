from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

from .models import Employee


def _load_pillow():
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    return Image, ImageDraw, ImageFont, ImageOps


def _font(size: int, bold: bool = False):
    _, _, ImageFont, _ = _load_pillow()
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _telegram_label(employee: Employee) -> str:
    username = (getattr(employee, "telegram_username", None) or "").strip()
    if username:
        return f"@{username.lstrip('@')}"
    return (employee.telegram_user_id or "").strip() or "Telegram не указан"


def _initials(full_name: Optional[str]) -> str:
    parts = [part for part in (full_name or "").strip().split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[1][:1]).upper()


def render_employee_card_png(employee: Employee) -> bytes:
    Image, ImageDraw, _, ImageOps = _load_pillow()

    width, height = 760, 270
    canvas = Image.new("RGBA", (width, height), "#f5f7fb")
    draw = ImageDraw.Draw(canvas)

    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((18, 24, width - 18, height - 24), radius=34, fill=(16, 24, 40, 22))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14)) if False else shadow
    canvas.alpha_composite(shadow, (0, 8))
    draw.rounded_rectangle((20, 20, width - 20, height - 28), radius=34, fill="white", outline="#edf1f6")

    avatar_size = 108
    avatar_box = (64, 54, 64 + avatar_size, 54 + avatar_size)
    profile_path = Path((getattr(employee, "profile_photo_path", None) or "").strip())
    if profile_path.is_file():
        avatar = Image.open(profile_path).convert("RGB")
        avatar = ImageOps.fit(avatar, (avatar_size, avatar_size), centering=(0.5, 0.5))
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        canvas.paste(avatar, avatar_box[:2], mask)
    else:
        draw.ellipse(avatar_box, fill="#dce6f3")
        draw.text((avatar_box[0] + 30, avatar_box[1] + 28), _initials(employee.full_name), fill="#41576f", font=_font(34, bold=True))

    name = (employee.full_name or "").strip() or "Сотрудник"
    position = (employee.desired_position or "").strip() or "Должность не указана"
    work_email = (getattr(employee, "work_email", None) or "").strip() or "Рабочая почта не указана"
    telegram = _telegram_label(employee)
    work_hours = (getattr(employee, "work_hours", None) or "").strip() or "Рабочие часы не указаны"

    draw.text((42, 182), name, fill="#20293c", font=_font(28, bold=True))
    draw.text((42, 220), position, fill="#8d98a8", font=_font(20))

    right_x = 370
    draw.text((right_x, 72), work_email, fill="#20293c", font=_font(24, bold=True))
    draw.text((right_x, 132), telegram, fill="#20293c", font=_font(23, bold=True))
    draw.line((right_x, 160, right_x + 150, 160), fill="#20293c", width=2)
    draw.text((right_x, 190), work_hours, fill="#20293c", font=_font(26, bold=True))

    buffer = BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()
