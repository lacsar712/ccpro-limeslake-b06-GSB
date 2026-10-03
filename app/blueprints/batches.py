from datetime import datetime
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Pond, SlakeBatch
from app.services.filter import SensitiveWordError, assert_notes_allowed

bp = Blueprint("batches", __name__, url_prefix="/batches")


def _form_echo(pond_id, started_raw, target, peak, notes):
    """新建校验失败时回显用户已填内容（不落库）。"""
    started_at = datetime.fromisoformat(started_raw) if started_raw else datetime.utcnow()
    return SimpleNamespace(
        pond_id=pond_id,
        started_at=started_at,
        target_temp_c=target,
        peak_temp_c=peak,
        notes=notes,
    )


@bp.route("/")
@login_required
def list_batches():
    batches = (
        SlakeBatch.query.join(Pond)
        .order_by(SlakeBatch.started_at.desc())
        .all()
    )
    return render_template("batches/list.html", batches=batches)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_batch():
    ponds = Pond.query.order_by(Pond.code).all()
    if request.method == "POST":
        pond_id = int(request.form["pond_id"])
        started_raw = request.form.get("started_at") or ""
        target = float(request.form.get("target_temp_c") or 80)
        peak_raw = (request.form.get("peak_temp_c") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        started_at = (
            datetime.fromisoformat(started_raw)
            if started_raw
            else datetime.utcnow()
        )
        peak = float(peak_raw) if peak_raw else None
        # 备注先于任何字段落库；命中则整笔拒绝，不得半插入
        try:
            assert_notes_allowed(notes)
        except SensitiveWordError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            echo = _form_echo(pond_id, started_raw, target, peak, notes)
            return render_template(
                "batches/form.html", ponds=ponds, batch=echo, original_notes=""
            )
        batch = SlakeBatch(
            pond_id=pond_id,
            started_at=started_at,
            target_temp_c=target,
            peak_temp_c=peak,
            notes=notes,
        )
        db.session.add(batch)
        db.session.commit()
        flash("熟化批次已登记", "ok")
        pond = db.session.get(Pond, pond_id)
        return redirect(
            url_for(
                "board.floor_plan",
                plant_id=pond.plant_id if pond else None,
                pond=pond_id,
            )
        )
    return render_template(
        "batches/form.html", ponds=ponds, batch=None, original_notes=""
    )


@bp.route("/<int:batch_id>/edit", methods=["GET", "POST"])
@login_required
def edit_batch(batch_id: int):
    batch = SlakeBatch.query.get_or_404(batch_id)
    ponds = Pond.query.order_by(Pond.code).all()
    if request.method == "POST":
        pond_id = int(request.form["pond_id"])
        started_raw = request.form.get("started_at") or ""
        target = float(request.form.get("target_temp_c") or 80)
        peak_raw = (request.form.get("peak_temp_c") or "").strip()
        peak = float(peak_raw) if peak_raw else None
        notes = (request.form.get("notes") or "").strip()
        # 行锁串行化并发修改：后到者按库里最新备注判定
        locked = (
            db.session.query(SlakeBatch)
            .filter_by(id=batch.id)
            .with_for_update()
            .populate_existing()
            .one()
        )
        # 备注相对原值未变更（含既有含词备注原样提交）时不拦，其余字段照常更新
        try:
            assert_notes_allowed(notes, locked.notes)
        except SensitiveWordError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return render_template(
                "batches/form.html", ponds=ponds, batch=batch, original_notes=batch.notes
            )
        locked.pond_id = pond_id
        if started_raw:
            locked.started_at = datetime.fromisoformat(started_raw)
        locked.target_temp_c = target
        locked.peak_temp_c = peak
        locked.notes = notes
        db.session.commit()
        flash("熟化批次已更新", "ok")
        return redirect(
            url_for(
                "board.floor_plan",
                plant_id=batch.pond.plant_id,
                pond=batch.pond_id,
            )
        )
    return render_template(
        "batches/form.html", ponds=ponds, batch=batch, original_notes=batch.notes
    )
