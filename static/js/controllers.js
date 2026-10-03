import { Application, Controller } from "https://unpkg.com/@hotwired/stimulus@3.2.2/dist/stimulus.js"

const application = Application.start()

class FlashController extends Controller {
  static targets = ["item"]
  connect() {
    window.setTimeout(() => {
      this.itemTargets.forEach((el) => {
        el.style.opacity = "0"
        el.style.transition = "opacity .4s"
      })
    }, 4000)
  }
}

class FormHintController extends Controller {
  static targets = ["status", "hint"]
  connect() {
    this.update()
    this.statusTarget?.addEventListener("change", () => this.update())
  }
  update() {
    if (!this.hasHintTarget || !this.hasStatusTarget) return
    if (this.statusTarget.value === "drawn") {
      this.hintTarget.textContent =
        "当前选择「已出灰」：须存在最近批次，且峰值温度已记录并 ≥ 60℃。"
    } else {
      this.hintTarget.textContent =
        "出灰前请确认最近熟化批次已记录峰值温度且不低于 60℃。"
    }
  }
}

class BoardController extends Controller {
  static targets = ["drawer", "backdrop"]
  static values = { open: Boolean }

  connect() {
    if (this.openValue) this._setOpen(true)
  }

  openDrawer() {
    // Navigation still loads selected pond; keep drawer state consistent on SPA-less click
    this._setOpen(true)
  }

  closeDrawer(event) {
    if (event) event.preventDefault()
    this._setOpen(false)
    const closeLink = event?.currentTarget
    if (closeLink?.href) {
      window.location.href = closeLink.href
    } else if (this.hasBackdropTarget) {
      const base = new URL(window.location.href)
      base.searchParams.delete("pond")
      window.location.href = base.toString()
    }
  }

  _setOpen(open) {
    this.openValue = open
    if (this.hasDrawerTarget) {
      this.drawerTarget.classList.toggle("is-open", open)
      this.drawerTarget.setAttribute("aria-hidden", open ? "false" : "true")
    }
    if (this.hasBackdropTarget) {
      this.backdropTarget.classList.toggle("is-open", open)
    }
  }
}

class SensitiveNotesController extends Controller {
  // 词库由页面以 JSON 注入（与后端校验同一批启用词），保证提示与落库结论一致
  static targets = ["notes", "hint"]
  static values = { words: Array, original: String }

  connect() {
    this.update()
    this.notesTarget?.addEventListener("input", () => this.update())
    this.element.addEventListener("submit", (event) => this.onSubmit(event))
  }

  // 备注与原值一致（编辑/抽屉中原样提交存量备注）时不判命中，
  // 与服务端一致：出灰、改池态、登记峰值不受词库影响
  isUnchanged() {
    return (this.notesTarget?.value || "") === (this.originalValue || "")
  }

  hitWord() {
    const value = this.notesTarget?.value || ""
    if (!value || this.isUnchanged()) return null
    const lowered = value.toLowerCase()
    for (const word of this.wordsValue) {
      if (word && lowered.includes(word.toLowerCase())) return word
    }
    return null
  }

  update() {
    if (!this.hasHintTarget) return
    const hit = this.hitWord()
    if (hit) {
      this.hintTarget.textContent = `备注命中敏感词「${hit}」，整笔记录将被拒绝保存`
      this.hintTarget.classList.add("hint-danger")
    } else {
      this.hintTarget.textContent = this.isUnchanged() && this.originalValue
        ? "备注未改动，保存不受敏感词库限制。"
        : "备注未命中启用敏感词，可正常保存。"
      this.hintTarget.classList.remove("hint-danger")
    }
  }

  onSubmit(event) {
    const hit = this.hitWord()
    if (hit) {
      event.preventDefault()
      this.update()
      this.notesTarget?.focus()
    }
  }
}

application.register("flash", FlashController)
application.register("form-hint", FormHintController)
application.register("board", BoardController)
application.register("sensitive-notes", SensitiveNotesController)
