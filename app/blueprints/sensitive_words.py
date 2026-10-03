from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import SensitiveWord

bp = Blueprint("sensitive_words", __name__, url_prefix="/sensitive-words")


@bp.route("/")
@login_required
def list_words():
    words = SensitiveWord.query.order_by(
        SensitiveWord.enabled.desc(), SensitiveWord.created_at.desc()
    ).all()
    enabled_count = sum(1 for w in words if w.enabled)
    return render_template(
        "sensitive_words/list.html",
        words=words,
        enabled_count=enabled_count,
    )


@bp.route("/", methods=["POST"])
@login_required
def create_word():
    word = (request.form.get("word") or "").strip()
    if not word:
        flash("敏感词不能为空", "error")
        return redirect(url_for("sensitive_words.list_words"))
    if len(word) > 100:
        flash("敏感词长度不能超过 100 个字符", "error")
        return redirect(url_for("sensitive_words.list_words"))
    existing = SensitiveWord.query.filter_by(word=word).first()
    if existing:
        if not existing.enabled:
            existing.enabled = True
            db.session.commit()
            flash(f"敏感词「{word}」已存在并已重新启用", "ok")
        else:
            flash(f"敏感词「{word}」已存在且启用中", "error")
        return redirect(url_for("sensitive_words.list_words"))
    db.session.add(SensitiveWord(word=word, enabled=True))
    db.session.commit()
    flash(f"敏感词「{word}」已添加并启用", "ok")
    return redirect(url_for("sensitive_words.list_words"))


@bp.route("/<int:word_id>/toggle", methods=["POST"])
@login_required
def toggle_word(word_id: int):
    word = SensitiveWord.query.get_or_404(word_id)
    word.enabled = not word.enabled
    db.session.commit()
    flash(
        f"敏感词「{word.word}」已{'启用' if word.enabled else '停用'}",
        "ok",
    )
    return redirect(url_for("sensitive_words.list_words"))


@bp.route("/<int:word_id>/delete", methods=["POST"])
@login_required
def delete_word(word_id: int):
    word = SensitiveWord.query.get_or_404(word_id)
    text = word.word
    db.session.delete(word)
    db.session.commit()
    flash(f"敏感词「{text}」已删除", "ok")
    return redirect(url_for("sensitive_words.list_words"))
