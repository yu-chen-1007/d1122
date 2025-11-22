# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time, timedelta
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "replace-with-your-secret"  # 上線請換成更安全的 key
db = SQLAlchemy(app)

# ---------------------------
# 資料模型
# ---------------------------
class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    student_id = db.Column(db.String(40), nullable=False)
    room = db.Column(db.String(20), nullable=False)
    date = db.Column(db.String(20), nullable=False)        # 格式：YYYY-MM-DD
    start_time = db.Column(db.String(10), nullable=False) # 格式：HH:MM
    end_time = db.Column(db.String(10), nullable=False)   # 格式：HH:MM

    def __repr__(self):
        return f"<Reservation {self.room} {self.date} {self.start_time}-{self.end_time}>"

with app.app_context():
    db.create_all()

# ---------------------------
# 工具：產生時段（08:00–23:00，每小時一格，最後一格 22:00-23:00）
# 回傳 list of tuples: [("08:00","09:00"), ...]
# ---------------------------
def generate_timeslots(start_hour=8, end_hour=23):
    slots = []
    current = datetime.combine(datetime.today(), time(start_hour, 0))
    end_dt = datetime.combine(datetime.today(), time(end_hour, 0))
    while current < end_dt:
        s = current.time().strftime("%H:%M")
        e = (current + timedelta(hours=1)).time().strftime("%H:%M")
        slots.append((s, e))
        current += timedelta(hours=1)
    return slots

# ---------------------------
# 檢查選取時段是否連續（selected: list of "HH:MM" strings）
# 若連續回 True，並回傳 (start, end) 字串；否則回 (False, message)
# ---------------------------
def check_continuous(selected):
    if not selected:
        return False, "請至少選擇一個時段。"
    # 轉成 time 物件並排序
    times = sorted([datetime.strptime(t, "%H:%M") for t in selected])
    # 檢查連續性（後一個必須等於前一個 + 1 小時）
    for i in range(1, len(times)):
        if (times[i] - times[i-1]) != timedelta(hours=1):
            return False, "選取的時段必須連續（不可跳格）。"
    start = times[0].time().strftime("%H:%M")
    end = (times[-1] + timedelta(hours=1)).time().strftime("%H:%M")
    return True, (start, end)

# ---------------------------
# 檢查是否與既有預約衝突（同 room、同 date）
# new_start/new_end are "HH:MM" strings
# ---------------------------
def has_conflict(room, date_str, new_start, new_end):
    # 取出該房該日所有現有預約
    existing = Reservation.query.filter_by(room=room, date=date_str).all()
    ns = datetime.strptime(new_start, "%H:%M").time()
    ne = datetime.strptime(new_end, "%H:%M").time()
    for r in existing:
        es = datetime.strptime(r.start_time, "%H:%M").time()
        ee = datetime.strptime(r.end_time, "%H:%M").time()
        # 檢查是否重疊： (new_start < existing_end) and (new_end > existing_start)
        if (ns < ee) and (ne > es):
            return True
    return False

# ---------------------------
# 首頁 / 預約表單（GET 顯示時段，POST 提交）
# ---------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    slots = generate_timeslots(8, 23)  # 08:00 - 23:00 => 最後時段 22:00-23:00
    rooms = ["A101", "A102", "B201"]   # 可客製化或從資料庫讀

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        room = request.form.get("room")
        date = request.form.get("date")
        selected_slots = request.form.getlist("slots")  # slot value = start time "HH:MM"

        # 基本欄位驗證
        if not (name and student_id and room and date):
            flash("請完整填寫姓名、學號、討論室與日期。", "danger")
            return redirect(url_for("index"))

        # 檢查連續時段
        ok, res = check_continuous(selected_slots)
        if not ok:
            flash(res, "danger")
            return redirect(url_for("index"))
        start_time, end_time = res  # strings "HH:MM"

        # 檢查與現有預約是否衝突
        if has_conflict(room, date, start_time, end_time):
            flash("⚠️ 時間衝突：該時段已被預約，請選擇其他時段。", "danger")
            return redirect(url_for("index"))

        # 全部 OK：建立預約
        new_r = Reservation(
            name=name,
            student_id=student_id,
            room=room,
            date=date,
            start_time=start_time,
            end_time=end_time
        )
        db.session.add(new_r)
        db.session.commit()
        flash(f"✅ 預約成功：{room} {date} {start_time}~{end_time}", "success")
        return redirect(url_for("reservations"))

    return render_template("index.html", slots=slots, rooms=rooms)

# ---------------------------
# 檢視所有預約
# ---------------------------
@app.route("/reservations")
def reservations():
    all_data = Reservation.query.order_by(Reservation.date, Reservation.start_time).all()
    return render_template("reservations.html", reservations=all_data)

# ---------------------------
# 刪除預約（簡單管理，若要安全請改為 POST + 驗證）
# ---------------------------
@app.route("/delete/<int:res_id>")
def delete(res_id):
    r = Reservation.query.get_or_404(res_id)
    db.session.delete(r)
    db.session.commit()
    flash("已刪除該筆預約。", "info")
    return redirect(url_for("reservations"))

if __name__ == "__main__":
    app.run(debug=True)
