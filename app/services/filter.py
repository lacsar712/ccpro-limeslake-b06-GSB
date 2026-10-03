"""批次备注敏感词过滤。

所有备注写入链路（批次保存、平面图抽屉）都必须经此校验，
保证两条路径结论一致：命中任一启用词则整笔拒绝，不得半插入。
"""

from __future__ import annotations

from app.extensions import db
from app.models import SensitiveWord


class SensitiveWordError(ValueError):
    """备注命中敏感词。"""


def enabled_words() -> list[str]:
    """当前启用的敏感词（去掉纯空白项，按长度降序便于提示时选最具体命中）。"""
    rows = db.session.query(SensitiveWord.word).filter(SensitiveWord.enabled.is_(True)).all()
    words = sorted({w for (w,) in rows if w and w.strip()}, key=len, reverse=True)
    return words


def find_hit(text: str, words: list[str] | None = None) -> str | None:
    """返回命中的第一个启用词；未命中返回 None。子串匹配，大小写不敏感。"""
    if not text:
        return None
    if words is None:
        words = enabled_words()
    lowered = text.lower()
    for word in words:  # 已按长度降序
        if word.lower() in lowered:
            return word
    return None


def assert_notes_allowed(new_notes: str, old_notes: str | None = None) -> None:
    """
    校验备注可写入。命中启用词抛 SensitiveWordError，调用方必须回滚整个事务。

    备注相对原值未变更（含对既有含词备注的原样提交）时放行，
    使登记峰值、出灰、改池态等非备注操作不受词库影响。
    """
    new_notes = new_notes or ""
    if old_notes is not None and new_notes == old_notes:
        return
    hit = find_hit(new_notes)
    if hit is not None:
        raise SensitiveWordError(f"备注命中敏感词「{hit}」，整笔记录已拒绝保存")
