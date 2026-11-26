"""
Outreach & WhatsApp link generation helpers for B2B contact follow-up.
"""
import re
from typing import Optional
from urllib.parse import quote

DEFAULT_WA_TEMPLATE_1 = (
    "Halo tim {nama_usaha}, perkenalkan saya dari tim solusi digital. "
    "Kami melihat profil {nama_usaha} di Google Maps dan ingin berdiskusi singkat "
    "mengenai cara membantu operasional bisnis Anda lebih efisien. Apakah ada waktu luang minggu ini?"
)

DEFAULT_WA_TEMPLATE_2 = (
    "Halo tim {nama_usaha}, izin follow up pesan saya sebelumnya ya. "
    "Apakah informasi mengenai solusi operasional untuk {nama_usaha} sudah sempat dibaca?"
)

DEFAULT_WA_TEMPLATE_3 = (
    "Selamat siang tim {nama_usaha}, ini pengingat terakhir dari kami. "
    "Jika {nama_usaha} tertarik mencoba demo gratis untuk mempermudah manajemen pelanggan, "
    "silakan balas pesan ini kapan saja. Terima kasih!"
)


def format_wa_phone(phone: Optional[str]) -> str:
    """
    Normalize a phone number into international WhatsApp digit format (e.g. 6281234567890).
    Returns empty string if the number is invalid or too short.
    """
    if not phone or not isinstance(phone, str):
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 8:
        return ""
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    return digits


def render_wa_message(template: str, business_name: str, category: str = "") -> str:
    """Safely substitute {nama_usaha}, {business_name}, and {kategori} placeholders."""
    msg = template or ""
    biz = (business_name or "Anda").strip()
    cat = (category or "bisnis Anda").strip()
    return (
        msg.replace("{nama_usaha}", biz)
        .replace("{business_name}", biz)
        .replace("{kategori}", cat)
        .replace("{category}", cat)
    )


def build_whatsapp_link(
    phone: Optional[str],
    template: str,
    business_name: str,
    category: str = "",
) -> Optional[str]:
    """Build a clickable https://wa.me/... URL with pre-filled encoded message."""
    wa_digits = format_wa_phone(phone)
    if not wa_digits:
        return None
    message = render_wa_message(template, business_name, category)
    return f"https://wa.me/{wa_digits}?text={quote(message)}"
