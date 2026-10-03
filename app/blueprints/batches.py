from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Pond, SlakeBatch
from app.services.rules import SensitiveWordError, assert_notes_allowed

bp = Blueprint("batches", __name__, url_prefix="/batches")


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

        # 词库关口在任何 INSERT 之前：命中即整笔拒绝，不得半插入
        try:
            assert_notes_allowed(notes)
        except SensitiveWordError as exc:
            flash(str(exc), "error")
            # 用瞬态对象回填表单，便于用户改词后重提；该对象绝不入库
            stale = SlakeBatch(
                pond_id=pond_id,
                started_at=datetime.fromisoformat(started_raw) if started_raw else datetime.utcnow(),
                target_temp_c=target,
                peak_temp_c=float(peak_raw) if peak_raw else None,
                notes=notes,
            )
            return render_template("batches/form.html", ponds=ponds, batch=stale)

        started_at = (
            datetime.fromisoformat(started_raw)
            if started_raw
            else datetime.utcnow()
        )
        peak = float(peak_raw) if peak_raw else None
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
    return render_template("batches/form.html", ponds=ponds, batch=None)


@bp.route("/<int:batch_id>/edit", methods=["GET", "POST"])
@login_required
def edit_batch(batch_id: int):
    if request.method == "POST":
        # 行锁串行化并发的备注保存：命中的一笔等合法笔提交后仍会判命中并回滚
        batch = (
            db.session.query(SlakeBatch)
            .filter_by(id=batch_id)
            .with_for_update()
            .one_or_none()
        )
        if batch is None:
            db.session.rollback()
            abort(404)

        pond_id = int(request.form["pond_id"])
        started_raw = request.form.get("started_at") or ""
        target = float(request.form.get("target_temp_c") or 80)
        peak_raw = (request.form.get("peak_temp_c") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        # 先校验后赋值：命中则本事务未改任何字段，回滚后原状不动
        try:
            assert_notes_allowed(notes)
        except SensitiveWordError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            ponds = Pond.query.order_by(Pond.code).all()
            stale = SlakeBatch(
                id=batch_id,
                pond_id=pond_id,
                started_at=datetime.fromisoformat(started_raw) if started_raw else batch.started_at,
                target_temp_c=target,
                peak_temp_c=float(peak_raw) if peak_raw else None,
                notes=notes,
            )
            return render_template("batches/form.html", ponds=ponds, batch=stale)

        batch.pond_id = pond_id
        if started_raw:
            batch.started_at = datetime.fromisoformat(started_raw)
        batch.target_temp_c = target
        batch.peak_temp_c = float(peak_raw) if peak_raw else None
        batch.notes = notes
        db.session.commit()
        flash("熟化批次已更新", "ok")
        return redirect(
            url_for(
                "board.floor_plan",
                plant_id=batch.pond.plant_id,
                pond=batch.pond_id,
            )
        )
    batch = SlakeBatch.query.get_or_404(batch_id)
    ponds = Pond.query.order_by(Pond.code).all()
    return render_template("batches/form.html", ponds=ponds, batch=batch)
