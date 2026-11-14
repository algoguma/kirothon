"""Small helpers for Telethon entities and messages."""

from telethon.tl.custom import Message as TgMessage
from telethon.tl.types import User as TgUser


def is_private_user(entity: object) -> bool:
    # Spec scope: 1:1 chats only; no bots, no "Saved Messages".
    return isinstance(entity, TgUser) and not entity.bot and not entity.is_self


def display_name(entity: TgUser) -> str:
    name = " ".join(part for part in (entity.first_name, entity.last_name) if part)
    return name or entity.username or str(entity.id)


def message_text(msg: TgMessage) -> str:
    """Text only (spec 6.4): media becomes a type tag, followed by the caption if any."""
    text = msg.message or ""
    if msg.media is None:
        return text
    if msg.photo:
        tag = "[사진]"
    elif msg.video or msg.gif:
        tag = "[동영상]"
    elif msg.voice or msg.audio:
        tag = "[음성]"
    elif msg.sticker:
        tag = "[스티커]"
    elif msg.document:
        tag = "[파일]"
    elif msg.web_preview:
        return text  # link preview: the text already has the link
    else:
        tag = "[미디어]"
    return f"{tag} {text}" if text else tag
