"""
model.py — MVC Model Layer
===========================
Wraps the database and business-logic helpers that already exist inside
claude_cs.py without touching a single line of that file.

All raw SQLite calls and pure-logic functions are exposed here so that
the Controller can call them by name instead of embedding SQL everywhere.
"""

import sqlite3
import random
from datetime import datetime

# ── Re-export the conversion helpers from the original module ──────────────
# These are pure functions with no side-effects; we just re-expose them.
from claude_cs import (
    gwa_to_gpa,
    gpa_to_gwa,
    gwa_to_percent,
    get_school_years,
    init_db,          # DB bootstrap is also part of the Model
)


# ════════════════════════════════════════════════════════════════════════════
# APPLICATION STATE  (Model state, not UI state)
# ════════════════════════════════════════════════════════════════════════════

class AppState:
    """
    Single source of truth for transient application state.
    The Controller reads and writes this; the View is given read-only access.
    """
    current_view: str = "login"
    current_user: tuple | None = None
    temp_email:   str | None = None
    temp_otp:     str | None = None
    form_state:   dict = {}


# ════════════════════════════════════════════════════════════════════════════
# USER MODEL
# ════════════════════════════════════════════════════════════════════════════

class UserModel:
    DB = "users.db"

    @staticmethod
    def authenticate(username: str, password: str) -> tuple | None:
        conn = sqlite3.connect(UserModel.DB)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",
                  (username, password))
        row = c.fetchone()
        conn.close()
        return row

    @staticmethod
    def register(username: str, full_name: str, email: str, password: str) -> bool:
        """Returns True on success, False if username already exists."""
        try:
            conn = sqlite3.connect(UserModel.DB)
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, full_name, email, password, bio) VALUES (?,?,?,?,?)",
                (username, full_name, email, password, "Student Profile"),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def find_by_email(email: str) -> tuple | None:
        conn = sqlite3.connect(UserModel.DB)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=?", (email,))
        row = c.fetchone()
        conn.close()
        return row

    @staticmethod
    def update_password(email: str, new_password: str) -> None:
        conn = sqlite3.connect(UserModel.DB)
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE email=?", (new_password, email))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all() -> list[tuple]:
        conn = sqlite3.connect(UserModel.DB)
        c = conn.cursor()
        c.execute("SELECT id, username, full_name, email, password, bio, role FROM users")
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def create(username: str, full_name: str, email: str,
               password: str, role: str) -> bool:
        try:
            conn = sqlite3.connect(UserModel.DB)
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, full_name, email, password, bio, role) VALUES (?,?,?,?,?,?)",
                (username, full_name, email, password, "New User Profile", role),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update(uid: int, username: str, full_name: str,
               email: str, password: str, role: str) -> bool:
        try:
            conn = sqlite3.connect(UserModel.DB)
            c = conn.cursor()
            c.execute(
                "UPDATE users SET username=?, full_name=?, email=?, password=?, role=? WHERE id=?",
                (username, full_name, email, password, role, uid),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete(uid: int) -> None:
        conn = sqlite3.connect(UserModel.DB)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# GRADE RECORDS MODEL
# ════════════════════════════════════════════════════════════════════════════

class GradeModel:
    DB = "users.db"

    @staticmethod
    def fetch(user_id: int, school_year: str, semester: str) -> list[tuple]:
        conn = sqlite3.connect(GradeModel.DB)
        c = conn.cursor()
        c.execute("""
            SELECT id, course_code, course_title, units, grade, status, remarks, faculty
            FROM grade_records
            WHERE user_id=? AND school_year=? AND semester=?
            ORDER BY id ASC
        """, (user_id, school_year, semester))
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def insert(user_id: int, school_year: str, semester: str,
               code: str, title: str, units: float,
               grade: str, status: str, remarks: str, faculty: str) -> None:
        conn = sqlite3.connect(GradeModel.DB)
        c = conn.cursor()
        c.execute("""
            INSERT INTO grade_records
            (user_id, school_year, semester, course_code, course_title,
             units, grade, status, remarks, faculty)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (user_id, school_year, semester, code, title,
              units, grade, status, remarks, faculty))
        conn.commit()
        conn.close()

    @staticmethod
    def update(rid: int, code: str, title: str, units: float,
               grade: str, status: str, remarks: str, faculty: str) -> None:
        conn = sqlite3.connect(GradeModel.DB)
        c = conn.cursor()
        c.execute("""
            UPDATE grade_records
            SET course_code=?, course_title=?, units=?, grade=?,
                status=?, remarks=?, faculty=?
            WHERE id=?
        """, (code, title, units, grade, status, remarks, faculty, rid))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(rid: int) -> None:
        conn = sqlite3.connect(GradeModel.DB)
        c = conn.cursor()
        c.execute("DELETE FROM grade_records WHERE id=?", (rid,))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_semester(user_id: int, school_year: str, semester: str) -> None:
        conn = sqlite3.connect(GradeModel.DB)
        c = conn.cursor()
        c.execute(
            "DELETE FROM grade_records WHERE user_id=? AND school_year=? AND semester=?",
            (user_id, school_year, semester),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def compute_gwa(records: list[tuple]) -> tuple[float, float | None]:
        """Returns (total_units, gwa_or_None)."""
        total_units = total_points = 0.0
        for r in records:
            try:
                g = float(r[4])
                u = float(r[3])
                total_units  += u
                total_points += g * u
            except (ValueError, TypeError):
                pass
        if total_units == 0:
            return total_units, None
        return total_units, total_points / total_units


# ════════════════════════════════════════════════════════════════════════════
# GWA HISTORY MODEL
# ════════════════════════════════════════════════════════════════════════════

class GwaHistoryModel:
    DB = "users.db"

    @staticmethod
    def fetch(user_id: int, limit: int = 20) -> list[tuple]:
        conn = sqlite3.connect(GwaHistoryModel.DB)
        c = conn.cursor()
        c.execute(
            "SELECT id, gwa, subjects, calc_date FROM gwa_history "
            "WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def insert(user_id: int, gwa: float, subjects_str: str) -> None:
        conn = sqlite3.connect(GwaHistoryModel.DB)
        c = conn.cursor()
        c.execute(
            "INSERT INTO gwa_history (user_id, gwa, subjects, calc_date) VALUES (?,?,?,?)",
            (user_id, round(gwa, 4), subjects_str, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def delete(hid: int) -> None:
        conn = sqlite3.connect(GwaHistoryModel.DB)
        c = conn.cursor()
        c.execute("DELETE FROM gwa_history WHERE id=?", (hid,))
        conn.commit()
        conn.close()

    @staticmethod
    def clear(user_id: int) -> None:
        conn = sqlite3.connect(GwaHistoryModel.DB)
        c = conn.cursor()
        c.execute("DELETE FROM gwa_history WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# NOTES MODEL
# ════════════════════════════════════════════════════════════════════════════

class NotesModel:
    DB = "users.db"

    @staticmethod
    def fetch(user_id: int, query: str = "") -> list[tuple]:
        conn = sqlite3.connect(NotesModel.DB)
        c = conn.cursor()
        if query:
            c.execute(
                "SELECT id, title, content, modified FROM notes "
                "WHERE user_id=? AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY modified DESC, id DESC",
                (user_id, f"%{query}%", f"%{query}%"),
            )
        else:
            c.execute(
                "SELECT id, title, content, modified FROM notes "
                "WHERE user_id=? ORDER BY modified DESC, id DESC",
                (user_id,),
            )
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def insert(user_id: int, title: str, content: str) -> None:
        now_str = datetime.now().isoformat()
        conn = sqlite3.connect(NotesModel.DB)
        c = conn.cursor()
        c.execute(
            "INSERT INTO notes (user_id, title, content, date, modified) VALUES (?,?,?,?,?)",
            (user_id, title, content, now_str, now_str),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def update(nid: int, title: str, content: str) -> None:
        conn = sqlite3.connect(NotesModel.DB)
        c = conn.cursor()
        c.execute(
            "UPDATE notes SET title=?, content=?, modified=? WHERE id=?",
            (title, content, datetime.now().isoformat(), nid),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def delete(nid: int) -> None:
        conn = sqlite3.connect(NotesModel.DB)
        c = conn.cursor()
        c.execute("DELETE FROM notes WHERE id=?", (nid,))
        conn.commit()
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# SCHEDULING MODEL
# ════════════════════════════════════════════════════════════════════════════

class ScheduleModel:
    DB = "users.db"

    # ── Lookups ────────────────────────────────────────────────────────────
    @staticmethod
    def get_teachers() -> list[tuple]:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("SELECT teacher_id, teacher_name FROM sched_teachers ORDER BY teacher_name")
        r = c.fetchall(); conn.close(); return r

    @staticmethod
    def get_subjects() -> list[tuple]:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("SELECT subject_id, subject_code, subject_title FROM sched_subjects ORDER BY subject_code")
        r = c.fetchall(); conn.close(); return r

    @staticmethod
    def get_rooms() -> list[tuple]:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("SELECT room_id, room_name FROM sched_rooms ORDER BY room_name")
        r = c.fetchall(); conn.close(); return r

    @staticmethod
    def get_schedules() -> list[tuple]:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("""
            SELECT s.schedule_id, t.teacher_name, sub.subject_code, sub.subject_title,
                   r.room_name, s.day, s.start_time, s.end_time,
                   s.teacher_id, s.subject_id, s.room_id
            FROM sched_schedules s
            JOIN sched_teachers t   ON s.teacher_id = t.teacher_id
            JOIN sched_subjects sub ON s.subject_id = sub.subject_id
            JOIN sched_rooms r      ON s.room_id    = r.room_id
            ORDER BY s.day, s.start_time
        """)
        r = c.fetchall(); conn.close(); return r

    # ── Conflict check ─────────────────────────────────────────────────────
    @staticmethod
    def check_conflict(room_id, teacher_id, day, start, end,
                       exclude_id=None) -> str | None:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        q = "SELECT * FROM sched_schedules WHERE room_id=? AND day=? AND start_time < ? AND end_time > ?"
        p = [room_id, day, end, start]
        if exclude_id:
            q += " AND schedule_id != ?"; p.append(exclude_id)
        c.execute(q, p)
        if c.fetchone():
            conn.close(); return "Room is already occupied during this time."
        q = "SELECT * FROM sched_schedules WHERE teacher_id=? AND day=? AND start_time < ? AND end_time > ?"
        p = [teacher_id, day, end, start]
        if exclude_id:
            q += " AND schedule_id != ?"; p.append(exclude_id)
        c.execute(q, p)
        if c.fetchone():
            conn.close(); return "Teacher already has a class during this time."
        conn.close(); return None

    # ── Schedule CRUD ──────────────────────────────────────────────────────
    @staticmethod
    def add_schedule(teacher_id, subject_id, room_id, day, start, end) -> None:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute(
            "INSERT INTO sched_schedules "
            "(teacher_id,subject_id,room_id,day,start_time,end_time) VALUES (?,?,?,?,?,?)",
            (teacher_id, subject_id, room_id, day, start, end),
        )
        conn.commit(); conn.close()

    @staticmethod
    def update_schedule(sid, teacher_id, subject_id, room_id, day, start, end) -> None:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute(
            "UPDATE sched_schedules "
            "SET teacher_id=?,subject_id=?,room_id=?,day=?,start_time=?,end_time=? "
            "WHERE schedule_id=?",
            (teacher_id, subject_id, room_id, day, start, end, sid),
        )
        conn.commit(); conn.close()

    @staticmethod
    def delete_schedule(sid) -> None:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("DELETE FROM sched_schedules WHERE schedule_id=?", (sid,))
        conn.commit(); conn.close()

    # ── Entity CRUD (teachers / subjects / rooms) ──────────────────────────
    @staticmethod
    def add_teacher(name: str) -> None:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("INSERT INTO sched_teachers (teacher_name) VALUES (?)", (name,))
        conn.commit(); conn.close()

    @staticmethod
    def add_subject(code: str, title: str) -> None:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("INSERT INTO sched_subjects (subject_code, subject_title) VALUES (?,?)",
                  (code, title))
        conn.commit(); conn.close()

    @staticmethod
    def add_room(name: str) -> None:
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute("INSERT INTO sched_rooms (room_name) VALUES (?)", (name,))
        conn.commit(); conn.close()

    @staticmethod
    def delete_entity(entity_type: str, eid: int) -> None:
        tbl = {"teachers": "sched_teachers", "subjects": "sched_subjects", "rooms": "sched_rooms"}
        pk  = {"teachers": "teacher_id",     "subjects": "subject_id",     "rooms": "room_id"}
        conn = sqlite3.connect(ScheduleModel.DB)
        c = conn.cursor()
        c.execute(f"DELETE FROM {tbl[entity_type]} WHERE {pk[entity_type]}=?", (eid,))
        conn.commit(); conn.close()


# ════════════════════════════════════════════════════════════════════════════
# OTP HELPER  (stateless; state lives in AppState)
# ════════════════════════════════════════════════════════════════════════════

def generate_otp() -> str:
    return str(random.randint(1000, 9999))
