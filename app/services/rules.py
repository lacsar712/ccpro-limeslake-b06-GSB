"""石灰熟化池业务规则。"""

from __future__ import annotations

from app.extensions import db
from app.models import Pond, SlakeBatch, SensitiveWord

MIN_PEAK_TEMP_FOR_DRAWN = 60.0


class RuleError(ValueError):
    """业务规则校验失败。"""


class SensitiveWordError(ValueError):
    """批次备注命中启用敏感词，该笔写入必须整体拒绝。"""

    def __init__(self, word: str):
        self.word = word
        super().__init__(f"备注命中敏感词「{word}」，整笔记录已拒绝且未保存")


def latest_batch_for_pond(pond: Pond, *, lock: bool = False) -> SlakeBatch | None:
    if not pond.batches:
        return None
    batch = max(pond.batches, key=lambda b: b.started_at)
    if lock:
        # 行锁串行化同一条批次的并发备注写入：
        # 命中的一笔等待合法笔提交后仍判命中并回滚，最终只留合法值。
        batch = (
            db.session.query(SlakeBatch)
            .filter_by(id=batch.id)
            .with_for_update()
            .one()
        )
    return batch


def can_mark_pond_drawn(pond: Pond) -> tuple[bool, str]:
    """
    熟化池转为「已出灰」(drawn) 的前提：
    最近一条熟化批次的峰值温度已记录，且 >= 60℃。
    """
    latest = latest_batch_for_pond(pond)
    if latest is None:
        return False, "该池尚无熟化批次，不能标记为已出灰"
    if latest.peak_temp_c is None:
        return False, "最近批次尚未记录峰值温度，不能标记为已出灰"
    if latest.peak_temp_c < MIN_PEAK_TEMP_FOR_DRAWN:
        return (
            False,
            f"最近批次峰值温度 {latest.peak_temp_c}℃ 低于 {MIN_PEAK_TEMP_FOR_DRAWN:.0f}℃，不能标记为已出灰",
        )
    return True, ""


def assert_can_set_pond_status(pond: Pond, new_status: str) -> None:
    if new_status not in Pond.STATUS_CHOICES:
        raise RuleError(f"无效状态：{new_status}")
    if new_status == Pond.STATUS_DRAWN:
        ok, msg = can_mark_pond_drawn(pond)
        if not ok:
            raise RuleError(msg)


def enabled_sensitive_words() -> list[str]:
    """当前启用的敏感词列表，按词长降序（命中提示优先取更具体的词）。"""
    rows = db.session.query(SensitiveWord.word).filter(
        SensitiveWord.enabled.is_(True)
    ).all()
    return sorted((w for (w,) in rows if w), key=len, reverse=True)


def find_sensitive_word(notes: str) -> str | None:
    """返回备注命中的第一个启用词；无命中返回 None。"""
    text = notes or ""
    for word in enabled_sensitive_words():
        if word in text:
            return word
    return None


def assert_notes_allowed(notes: str) -> None:
    """
    批次备注写入前的强制关口：命中任一启用词即抛 SensitiveWordError。
    调用方必须整笔回滚，严禁先落其它字段或半插入。
    """
    word = find_sensitive_word(notes)
    if word is not None:
        raise SensitiveWordError(word)
