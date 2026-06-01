import flet as ft
import sqlite3
import random
from datetime import datetime

# ──────────────────────────────────────────────
# Global State
# ──────────────────────────────────────────────
current_view = "login"
current_user = None
temp_email   = None
temp_otp     = None

form_state: dict = {}


# ──────────────────────────────────────────────
# Database Setup
# ──────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT UNIQUE,
            full_name TEXT,
            email     TEXT,
            password  TEXT,
            bio       TEXT,
            role      TEXT DEFAULT 'user'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            title      TEXT,
            content    TEXT,
            date       TEXT,
            modified   TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS gwa_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            gwa        REAL,
            subjects   TEXT,
            calc_date  TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS grade_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            school_year TEXT,
            semester    TEXT,
            course_code TEXT,
            course_title TEXT,
            units       REAL,
            grade       TEXT,
            status      TEXT,
            remarks     TEXT,
            faculty     TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # ── Class Scheduling Tables ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS sched_teachers (
            teacher_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_name TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sched_subjects (
            subject_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code  TEXT NOT NULL,
            subject_title TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sched_rooms (
            room_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sched_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id  INTEGER NOT NULL,
            subject_id  INTEGER NOT NULL,
            room_id     INTEGER NOT NULL,
            day         TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES sched_teachers(teacher_id),
            FOREIGN KEY(subject_id) REFERENCES sched_subjects(subject_id),
            FOREIGN KEY(room_id)    REFERENCES sched_rooms(room_id)
        )
    """)

    # Migrations
    c.execute("PRAGMA table_info(users)")
    cols = [col[1] for col in c.fetchall()]
    if "role" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

    c.execute("PRAGMA table_info(notes)")
    ncols = [col[1] for col in c.fetchall()]
    if "modified" not in ncols:
        c.execute("ALTER TABLE notes ADD COLUMN modified TEXT")

    # Default accounts
    c.execute("SELECT COUNT(*) FROM users WHERE username IN ('admin','user')")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT OR IGNORE INTO users (username, full_name, email, password, bio, role) VALUES (?,?,?,?,?,?)",
            ("admin", "Administrator", "admin@social.io", "password123", "System Administrator", "admin"),
        )
        c.execute(
            "INSERT OR IGNORE INTO users (username, full_name, email, password, bio, role) VALUES (?,?,?,?,?,?)",
            ("user", "John Doe", "john@social.io", "pass", "Standard User Profile", "user"),
        )

    # Seed scheduling data
    c.execute("SELECT COUNT(*) FROM sched_teachers")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO sched_teachers (teacher_name) VALUES (?)", [
            ("Mr. John Reyes",), ("Ms. Anna Santos",), ("Dr. Maria Cruz",), ("Engr. Carlo Dela Peña",)
        ])
    c.execute("SELECT COUNT(*) FROM sched_subjects")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO sched_subjects (subject_code, subject_title) VALUES (?, ?)", [
            ("IT101", "Introduction to Computing"),
            ("IT102", "Computer Programming 1"),
            ("IT201", "Data Structures"),
            ("IT301", "Database Management System"),
        ])
    c.execute("SELECT COUNT(*) FROM sched_rooms")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO sched_rooms (room_name) VALUES (?)", [
            ("Computer Laboratory 1",), ("Computer Laboratory 2",),
            ("Lecture Room 101",),      ("Lecture Room 102",),
        ])

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# GPA / GWA Conversion helpers
# ──────────────────────────────────────────────
def gwa_to_gpa(gwa: float) -> float:
    if gwa <= 1.0:    return 4.0
    elif gwa <= 1.25: return 3.75
    elif gwa <= 1.5:  return 3.5
    elif gwa <= 1.75: return 3.25
    elif gwa <= 2.0:  return 3.0
    elif gwa <= 2.25: return 2.75
    elif gwa <= 2.5:  return 2.5
    elif gwa <= 2.75: return 2.25
    elif gwa <= 3.0:  return 2.0
    elif gwa <= 3.5:  return 1.5
    elif gwa <= 4.0:  return 1.0
    else:             return 0.0

def gpa_to_gwa(gpa: float) -> float:
    if gpa >= 4.0:    return 1.0
    elif gpa >= 3.75: return 1.25
    elif gpa >= 3.5:  return 1.5
    elif gpa >= 3.25: return 1.75
    elif gpa >= 3.0:  return 2.0
    elif gpa >= 2.75: return 2.25
    elif gpa >= 2.5:  return 2.5
    elif gpa >= 2.25: return 2.75
    elif gpa >= 2.0:  return 3.0
    elif gpa >= 1.5:  return 3.5
    elif gpa >= 1.0:  return 4.0
    else:             return 5.0

def gwa_to_percent(gwa: float) -> float:
    table = {
        1.00: 99, 1.25: 96, 1.50: 93, 1.75: 90,
        2.00: 87, 2.25: 84, 2.50: 81, 2.75: 78,
        3.00: 75, 4.00: 70, 5.00: 60,
    }
    nearest = min(table.keys(), key=lambda k: abs(k - gwa))
    return table[nearest]


# ──────────────────────────────────────────────
# Generate school years dropdown options
# ──────────────────────────────────────────────
def get_school_years():
    current_year = datetime.now().year
    years = []
    for y in range(current_year - 5, current_year + 3):
        years.append(f"AY {y}-{y+1}")
    return years


# ──────────────────────────────────────────────
# Main App
# ──────────────────────────────────────────────
def main(page: ft.Page):
    init_db()

    page.title  = "College Grade System"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width   = 460
    page.window.height  = 860
    page.window.min_width  = 460
    page.window.min_height = 860
    page.bgcolor = "#030612"
    page.scroll  = ft.ScrollMode.AUTO
    page.vertical_alignment   = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.fonts = {
        "Outfit": "https://github.com/google/fonts/raw/main/ofl/outfit/Outfit-VariableFont_wght.ttf"
    }
    page.window.center()

    # ── Helpers ──────────────────────────────────
    def show_snack(msg: str, color: str = "cyan700"):
        sb = ft.SnackBar(content=ft.Text(msg), bgcolor=color, open=True)
        page.overlay.append(sb)
        page.update()

    def show_dialog(dialog):
        page.show_dialog(dialog)

    def close_dialog(_=None):
        page.pop_dialog()
        page.update()

    def _save_form_state():
        global form_state
        form_state = {}
        def _walk(ctrl):
            if isinstance(ctrl, ft.TextField) and ctrl.data:
                form_state[ctrl.data] = ctrl.value
            for child in getattr(ctrl, "controls", []) or []:
                _walk(child)
            for child in [getattr(ctrl, "content", None)]:
                if child:
                    _walk(child)
        for c in page.controls:
            _walk(c)

    def _r(key: str, default: str = "") -> str:
        return form_state.get(key, default)

    # ══════════════════════════════════════════════
    # NAVIGATION
    # ══════════════════════════════════════════════
    def navigate_to(view_name: str):
        global current_view, current_user, temp_email, temp_otp, form_state
        if view_name != current_view:
            form_state = {}
        current_view = view_name
        page.clean()

        # ── Always dark ──
        text_color    = "white"
        subtext_color = "#ffffff60"
        card_color    = "#0d111e"
        border_color  = "#ffffff15"
        shadow_color  = "#000000aa"
        row_bg        = "#161b2e"
        accent        = "#22d3ee"
        accent_dark   = "#0891b2"

        content = ft.Column(
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ─────────────────────────────────────────
        # LOGIN
        # ─────────────────────────────────────────
        if view_name == "login":
            user_input = ft.TextField(
                label="Username", prefix_icon=ft.Icons.PERSON_OUTLINE,
                border_radius=14, color=text_color,
                data="login_username", value=_r("login_username"),
            )
            pass_input = ft.TextField(
                label="Password", prefix_icon=ft.Icons.LOCK_OUTLINE,
                password=True, can_reveal_password=True,
                border_radius=14, color=text_color,
                data="login_password", value=_r("login_password"),
            )
            error_msg = ft.Text("", color="red400", size=12, visible=False)

            def login_click(e):
                global current_user
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM users WHERE username=? AND password=?",
                    (user_input.value, pass_input.value),
                )
                row = c.fetchone()
                conn.close()
                if row:
                    current_user = row
                    navigate_to("admin_dashboard" if row[6] == "admin" else "profile")
                else:
                    error_msg.value   = "Invalid username or password"
                    error_msg.visible = True
                    page.update()

            content.controls = [
                ft.Text("Log In", size=34, font_family="Outfit", weight="bold", color=text_color),
                user_input,
                pass_input,
                error_msg,
                ft.ElevatedButton(
                    "Authenticate", width=380, height=52,
                    bgcolor="white",
                    color="black",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                    on_click=login_click,
                ),
                ft.TextButton("Forgot Password?", on_click=lambda _: navigate_to("forgot_password")),
                ft.Row(
                    [ft.Text("New?", color=subtext_color),
                     ft.TextButton("Sign Up", on_click=lambda _: navigate_to("signup"))],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ]

        # ─────────────────────────────────────────
        # SIGN UP
        # ─────────────────────────────────────────
        elif view_name == "signup":
            un = ft.TextField(label="Username",  border_radius=14, color=text_color, data="su_un", value=_r("su_un"))
            fn = ft.TextField(label="Full Name", border_radius=14, color=text_color, data="su_fn", value=_r("su_fn"))
            em = ft.TextField(label="Email",     border_radius=14, color=text_color, data="su_em", value=_r("su_em"))
            pw = ft.TextField(label="Password",  password=True, can_reveal_password=True, border_radius=14, color=text_color, data="su_pw", value=_r("su_pw"))

            def register(e):
                if not un.value or not pw.value:
                    show_snack("Username and Password are required!", "red700")
                    return
                try:
                    conn = sqlite3.connect("users.db")
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO users (username, full_name, email, password, bio) VALUES (?,?,?,?,?)",
                        (un.value, fn.value, em.value, pw.value, "Student Profile"),
                    )
                    conn.commit(); conn.close()
                    show_snack("Account created! Please log in.")
                    navigate_to("login")
                except sqlite3.IntegrityError:
                    show_snack("Username already exists!", "red700")

            content.controls = [
                ft.Text("Sign Up", size=34, font_family="Outfit", weight="bold", color=text_color),
                un, fn, em, pw,
                ft.ElevatedButton(
                    "Register", width=380, height=52,
                    bgcolor=accent_dark, color="white",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                    on_click=register,
                ),
                ft.TextButton("Back to Login", on_click=lambda _: navigate_to("login")),
            ]

        # ─────────────────────────────────────────
        # USER DASHBOARD
        # ─────────────────────────────────────────
        elif view_name == "profile":
            def make_dash_btn(label, icon, dest):
                return ft.Container(
                    width=380,
                    height=70,
                    border_radius=18,
                    bgcolor=row_bg,
                    border=ft.border.all(1, border_color),
                    padding=ft.padding.symmetric(horizontal=24),
                    on_click=lambda _, d=dest: navigate_to(d),
                    content=ft.Row([
                        ft.Icon(icon, color=accent, size=26),
                        ft.Text(label, size=17, weight="w600", color=text_color),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, color=subtext_color),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                )

            content.controls = [
                ft.Row([
                    ft.Column([
                        ft.Text("Dashboard", size=26, font_family="Outfit", weight="bold", color=text_color),
                        ft.Text(f"Welcome back, {current_user[1]}", size=13, color=subtext_color),
                    ], spacing=2),
                    ft.IconButton(ft.Icons.LOGOUT, icon_color=subtext_color, on_click=lambda _: navigate_to("login")),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=1, color=border_color),
                make_dash_btn("My Grades",        ft.Icons.GRADE_OUTLINED,         "my_grades"),
                make_dash_btn("Grade Calculator", ft.Icons.CALCULATE_OUTLINED,     "grade_calc"),
                make_dash_btn("My Notes",         ft.Icons.STICKY_NOTE_2_OUTLINED, "notes"),
                make_dash_btn("Class Schedule",   ft.Icons.CALENDAR_MONTH_OUTLINED,"class_schedule"),
            ]

        # ─────────────────────────────────────────
        # MY GRADES  (CRUD - no dropdowns)
        # ─────────────────────────────────────────
        elif view_name == "my_grades":
            school_years = get_school_years()

            sel = {
                "sy":  school_years[-3] if len(school_years) >= 3 else school_years[-1],
                "sem": "2ND-SEM",
            }

            grades_table = ft.Column(spacing=0)
            summary_row  = ft.Row(spacing=16)

            sy_field = ft.TextField(
                value=sel["sy"],
                label="School Year",
                border_radius=12,
                color=text_color,
                bgcolor=row_bg,
                width=170,
                text_size=13,
                hint_text="e.g. AY 2025-2026",
            )
            sem_field = ft.TextField(
                value=sel["sem"],
                label="Semester",
                border_radius=12,
                color=text_color,
                bgcolor=row_bg,
                width=140,
                text_size=13,
                hint_text="1ST-SEM",
            )

            def apply_period(e):
                sel["sy"]  = sy_field.value.strip() or sel["sy"]
                sel["sem"] = sem_field.value.strip() or sel["sem"]
                refresh_table()

            def fetch_records():
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                c.execute("""
                    SELECT id, course_code, course_title, units, grade, status, remarks, faculty
                    FROM grade_records
                    WHERE user_id=? AND school_year=? AND semester=?
                    ORDER BY id ASC
                """, (current_user[0], sel["sy"], sel["sem"]))
                rows = c.fetchall()
                conn.close()
                return rows

            def compute_gwa(records):
                total_units  = 0.0
                total_points = 0.0
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

            def refresh_table():
                grades_table.controls.clear()
                records = fetch_records()

                def hcell(txt, flex=1):
                    return ft.Container(
                        expand=flex,
                        content=ft.Text(txt, size=11, weight="bold", color=subtext_color),
                        padding=ft.padding.symmetric(horizontal=6, vertical=10),
                    )

                grades_table.controls.append(
                    ft.Container(
                        bgcolor="#0a0e1a",
                        border_radius=ft.border_radius.only(top_left=12, top_right=12),
                        content=ft.Row([
                            hcell("CODE",    1),
                            hcell("TITLE",   3),
                            hcell("UNITS",   1),
                            hcell("GRADE",   1),
                            hcell("STATUS",  2),
                            hcell("FACULTY", 2),
                            hcell("",        2),
                        ], spacing=0),
                        border=ft.border.only(bottom=ft.BorderSide(1, border_color)),
                    )
                )

                if not records:
                    grades_table.controls.append(
                        ft.Container(
                            bgcolor=row_bg,
                            border_radius=ft.border_radius.only(bottom_left=12, bottom_right=12),
                            padding=40,
                            content=ft.Column([
                                ft.Icon(ft.Icons.GRADE_OUTLINED, size=40, color=subtext_color),
                                ft.Text("No records yet. Add a subject!", color=subtext_color, size=13),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                            alignment=ft.Alignment(0, 0),
                        )
                    )
                else:
                    for i, r in enumerate(records):
                        rid, code, title, units, grade, status, remark, faculty = r
                        is_last = (i == len(records) - 1)

                        def cell(txt, flex=1, bold=False, col=None):
                            return ft.Container(
                                expand=flex,
                                content=ft.Text(
                                    str(txt) if txt else "—",
                                    size=12,
                                    weight="bold" if bold else "normal",
                                    color=col or text_color,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                padding=ft.padding.symmetric(horizontal=6, vertical=12),
                            )

                        grade_color = text_color
                        try:
                            gv = float(grade)
                            if gv <= 1.5:   grade_color = "#4ade80"
                            elif gv <= 2.5: grade_color = accent
                            elif gv <= 3.0: grade_color = "#facc15"
                            else:           grade_color = "#f87171"
                        except (ValueError, TypeError):
                            pass

                        status_color = subtext_color
                        if status == "Passed":   status_color = "#4ade80"
                        elif status == "Failed": status_color = "#f87171"

                        grades_table.controls.append(
                            ft.Container(
                                bgcolor=row_bg if i % 2 == 0 else "#121627",
                                border_radius=ft.border_radius.only(
                                    bottom_left=12  if is_last else 0,
                                    bottom_right=12 if is_last else 0,
                                ),
                                border=ft.border.only(bottom=ft.BorderSide(1, border_color)) if not is_last else None,
                                content=ft.Row([
                                    cell(code,    1, bold=True, col=accent),
                                    cell(title,   3),
                                    cell(units,   1),
                                    cell(grade,   1, bold=True, col=grade_color),
                                    cell(status,  2, col=status_color),
                                    cell(faculty, 2, col=subtext_color),
                                    ft.Container(
                                        expand=2,
                                        content=ft.Row([
                                            ft.IconButton(
                                                ft.Icons.EDIT_OUTLINED,
                                                icon_color="blue400", icon_size=16,
                                                tooltip="Edit",
                                                on_click=lambda e, rec=r: open_record_modal(rec),
                                            ),
                                            ft.IconButton(
                                                ft.Icons.DELETE_OUTLINE,
                                                icon_color="red400", icon_size=16,
                                                tooltip="Delete",
                                                on_click=lambda e, r_id=rid: delete_record(r_id),
                                            ),
                                        ], spacing=0),
                                    ),
                                ], spacing=0),
                            )
                        )

                total_u, gwa = compute_gwa(records)
                gwa_text = f"GWA: {gwa:.2f}" if gwa is not None else "GWA: —"
                gpa_text = f"  |  GPA: {gwa_to_gpa(gwa):.2f}" if gwa is not None else ""
                summary_row.controls = [
                    ft.Container(
                        bgcolor="#0a0e1a",
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        content=ft.Row([
                            ft.Text(f"Total Units: {total_u:.1f}", size=13, weight="bold", color=text_color),
                            ft.Text(gwa_text + gpa_text, size=13, weight="bold", color=accent),
                        ], spacing=24),
                    ),
                ]
                page.update()

            def open_record_modal(edit_rec=None):
                is_edit = edit_rec is not None

                def styled_field(lbl, hint="", value="", num=False, expand=1):
                    return ft.TextField(
                        label=lbl,
                        hint_text=hint,
                        value=value,
                        border_radius=10,
                        color=text_color,
                        bgcolor="#1a1f35",
                        border_color="#ffffff20",
                        focused_border_color=accent,
                        label_style=ft.TextStyle(color=subtext_color, size=12),
                        text_size=14,
                        expand=expand,
                        keyboard_type=ft.KeyboardType.NUMBER if num else ft.KeyboardType.TEXT,
                        content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
                    )

                code_f    = styled_field("Course Code",    "e.g. CS 101",       value=edit_rec[1] if is_edit else "",                            expand=2)
                units_f   = styled_field("Units",          "3.0",               value=str(edit_rec[3]) if is_edit else "3.0",    num=True,        expand=1)
                title_f   = styled_field("Course Title",   "e.g. Calculus 1",   value=edit_rec[2] if is_edit else "")
                grade_f   = styled_field("Grade",          "1.00 – 5.00 / INC", value=str(edit_rec[4]) if is_edit and edit_rec[4] else "", num=False, expand=1)
                status_f  = styled_field("Status",         "Passed / Failed / INC / Dropped", value=edit_rec[5] if is_edit and edit_rec[5] else "", expand=1)
                remarks_f = styled_field("Remarks",        "Regular / Irregular",value=edit_rec[6] if is_edit and edit_rec[6] else "", expand=1)
                faculty_f = styled_field("Faculty Name",   "Last, First M.",    value=edit_rec[7] if is_edit else "")

                def section_label(txt):
                    return ft.Text(txt, size=11, weight="bold", color=subtext_color)

                def save_record(e):
                    if not code_f.value or not title_f.value:
                        show_snack("Course Code and Title are required!", "red700")
                        return
                    try:
                        units_val = float(units_f.value or 0)
                    except ValueError:
                        show_snack("Enter a valid unit number!", "red700")
                        return

                    conn = sqlite3.connect("users.db")
                    c = conn.cursor()
                    if is_edit:
                        c.execute("""
                            UPDATE grade_records
                            SET course_code=?, course_title=?, units=?, grade=?,
                                status=?, remarks=?, faculty=?
                            WHERE id=?
                        """, (code_f.value, title_f.value, units_val,
                              grade_f.value, status_f.value, remarks_f.value,
                              faculty_f.value, edit_rec[0]))
                    else:
                        c.execute("""
                            INSERT INTO grade_records
                            (user_id, school_year, semester, course_code, course_title,
                             units, grade, status, remarks, faculty)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (current_user[0], sel["sy"], sel["sem"],
                              code_f.value, title_f.value, units_val,
                              grade_f.value, status_f.value, remarks_f.value,
                              faculty_f.value))
                    conn.commit()
                    conn.close()
                    close_dialog()
                    refresh_table()

                dlg = ft.AlertDialog(
                    modal=True,
                    bgcolor="#0d111e",
                    title=ft.Container(
                        content=ft.Row([
                            ft.Container(width=4, height=28, border_radius=4, bgcolor=accent),
                            ft.Text("Edit Subject" if is_edit else "Add Subject", size=18, weight="bold", color=text_color),
                        ], spacing=10),
                        padding=ft.padding.only(bottom=4),
                    ),
                    content=ft.Container(
                        width=370,
                        padding=ft.padding.only(top=4),
                        content=ft.Column([
                            section_label("COURSE INFO"),
                            ft.Row([code_f, units_f], spacing=10),
                            title_f,
                            ft.Divider(height=1, color="#ffffff10"),
                            section_label("GRADE & STATUS"),
                            ft.Row([grade_f, status_f], spacing=10),
                            remarks_f,
                            ft.Divider(height=1, color="#ffffff10"),
                            section_label("FACULTY"),
                            faculty_f,
                        ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
                    ),
                    actions=[
                        ft.TextButton("Cancel", style=ft.ButtonStyle(color=subtext_color), on_click=lambda _: close_dialog()),
                        ft.ElevatedButton(
                            "Update" if is_edit else "Add Subject",
                            bgcolor=accent_dark, color="white",
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                            on_click=save_record,
                        ),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                show_dialog(dlg)

            def delete_record(rid):
                def confirm(e):
                    conn = sqlite3.connect("users.db")
                    c = conn.cursor()
                    c.execute("DELETE FROM grade_records WHERE id=?", (rid,))
                    conn.commit(); conn.close()
                    close_dialog(); refresh_table()

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Delete Subject"),
                    content=ft.Text("Remove this subject from your grades?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
                        ft.TextButton("Delete", style=ft.ButtonStyle(color="red"), on_click=confirm),
                    ],
                )
                show_dialog(dlg)

            def delete_all_records(e):
                def confirm(e2):
                    conn = sqlite3.connect("users.db")
                    c = conn.cursor()
                    c.execute("DELETE FROM grade_records WHERE user_id=? AND school_year=? AND semester=?",
                              (current_user[0], sel["sy"], sel["sem"]))
                    conn.commit(); conn.close()
                    close_dialog(); refresh_table()

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Clear All"),
                    content=ft.Text("Delete ALL subjects for this semester?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
                        ft.TextButton("Delete All", style=ft.ButtonStyle(color="red"), on_click=confirm),
                    ],
                )
                show_dialog(dlg)

            refresh_table()

            content.controls = [
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: navigate_to("profile"), icon_color=text_color),
                    ft.Text("My Grades", size=22, font_family="Outfit", weight="bold", color=text_color),
                    ft.IconButton(ft.Icons.DELETE_SWEEP_OUTLINED, icon_color="red400", tooltip="Clear semester", on_click=delete_all_records),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(
                    bgcolor=row_bg, border_radius=14,
                    border=ft.border.all(1, border_color),
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    content=ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, color=accent, size=18),
                        sy_field, sem_field,
                        ft.IconButton(ft.Icons.CHECK_CIRCLE_OUTLINE, icon_color=accent, tooltip="Apply period", on_click=apply_period),
                    ], spacing=8),
                ),
                ft.Divider(height=1, color=border_color),
                ft.Container(
                    content=ft.Row([ft.Container(content=grades_table, expand=True)], scroll=ft.ScrollMode.AUTO),
                    border_radius=14, border=ft.border.all(1, border_color),
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                ),
                summary_row,
                ft.ElevatedButton(
                    "＋ Add Subject", width=380, height=48,
                    bgcolor=accent_dark, color="white",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                    icon=ft.Icons.ADD,
                    on_click=lambda _: open_record_modal(None),
                ),
            ]

        # ─────────────────────────────────────────
        # GWA CALCULATOR
        # ─────────────────────────────────────────
        elif view_name == "grade_calc":
            rows_container = ft.Column(spacing=6)
            gwa_result_val = [0.0]
            gwa_display    = ft.Text("GWA: —", size=22, weight="bold", color=accent)
            history_col    = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=220)

            def make_row():
                sub   = ft.TextField(hint_text="Subject", text_size=12, height=42, border_radius=8, expand=2, bgcolor=row_bg, color=text_color)
                units = ft.TextField(hint_text="Units",   text_size=12, height=42, border_radius=8, expand=1, bgcolor=row_bg, color=text_color, keyboard_type=ft.KeyboardType.NUMBER)
                grade = ft.TextField(hint_text="Grade",   text_size=12, height=42, border_radius=8, expand=1, bgcolor=row_bg, color=text_color, keyboard_type=ft.KeyboardType.NUMBER)
                row_ref = ft.Row(
                    controls=[sub, units, grade,
                               ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_color="red400", icon_size=20,
                                             on_click=lambda e, r=None: remove_row(row_ref))],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
                return row_ref

            def remove_row(rr):
                if rr in rows_container.controls:
                    rows_container.controls.remove(rr)
                page.update()

            def add_row(e):
                rows_container.controls.append(make_row())
                page.update()

            def load_history():
                history_col.controls.clear()
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                c.execute("SELECT id, gwa, subjects, calc_date FROM gwa_history WHERE user_id=? ORDER BY id DESC LIMIT 20", (current_user[0],))
                rows_h = c.fetchall()
                conn.close()
                if not rows_h:
                    history_col.controls.append(ft.Text("No history yet.", size=12, color=subtext_color, text_align=ft.TextAlign.CENTER))
                else:
                    for hid, hgwa, hsubjects, hdate in rows_h:
                        try:
                            dt = datetime.fromisoformat(hdate)
                            date_str = dt.strftime("%b %d, %Y  %I:%M %p").lstrip("0")
                        except Exception:
                            date_str = hdate[:16]
                        history_col.controls.append(
                            ft.Container(
                                bgcolor=row_bg, border_radius=12,
                                border=ft.border.all(1, border_color),
                                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                                content=ft.Row([
                                    ft.Column([
                                        ft.Text(f"GWA: {hgwa:.2f}", weight="bold", size=15, color=accent),
                                        ft.Text(hsubjects, size=11, color=subtext_color, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(date_str, size=10, color=subtext_color),
                                    ], expand=True, spacing=3),
                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", icon_size=18,
                                                  on_click=lambda e, hid=hid: delete_history(hid)),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            )
                        )
                page.update()

            def delete_history(hid):
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                c.execute("DELETE FROM gwa_history WHERE id=?", (hid,))
                conn.commit(); conn.close()
                load_history()

            def clear_all_history():
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                c.execute("DELETE FROM gwa_history WHERE user_id=?", (current_user[0],))
                conn.commit(); conn.close()
                load_history()

            def calculate_gwa(e):
                total_u = total_p = 0.0
                subject_parts = []
                try:
                    for row in rows_container.controls:
                        sub_name = row.controls[0].value or "—"
                        u = float(row.controls[1].value or 0)
                        g = float(row.controls[2].value or 0)
                        if u > 0:
                            total_u += u; total_p += u * g
                            subject_parts.append(f"{sub_name}({int(u)}u, {g}g)")
                    if total_u == 0:
                        show_snack("Add at least one subject with units!", "red700"); return
                    gwa = total_p / total_u
                    gwa_result_val[0] = gwa
                    gwa_display.value = f"GWA: {gwa:.2f}"
                    subjects_str = ";  ".join(subject_parts)
                    conn = sqlite3.connect("users.db")
                    c = conn.cursor()
                    c.execute("INSERT INTO gwa_history (user_id, gwa, subjects, calc_date) VALUES (?,?,?,?)",
                              (current_user[0], round(gwa, 4), subjects_str, datetime.now().isoformat()))
                    conn.commit(); conn.close()
                    load_history()
                except ValueError:
                    show_snack("Enter valid numbers!", "red700")
                page.update()

            def reset_calc(e):
                rows_container.controls.clear()
                rows_container.controls.append(make_row())
                gwa_result_val[0] = 0.0
                gwa_display.value = "GWA: —"
                page.update()

            def show_gpa_to_gwa_dialog(e):
                inp = ft.TextField(label="Enter US GPA (0.0 – 4.0)", border_radius=12, keyboard_type=ft.KeyboardType.NUMBER, color=text_color)
                result = ft.Text("", color=accent, size=16, weight="bold")
                def convert(e2):
                    try:
                        val = float(inp.value)
                        result.value = "⚠ GPA must be between 0.0 and 4.0" if not 0.0 <= val <= 4.0 else f"GWA ≈ {gpa_to_gwa(val):.2f}"
                    except ValueError:
                        result.value = "⚠ Invalid number"
                    page.update()
                show_dialog(ft.AlertDialog(modal=True, title=ft.Text("GPA → GWA", weight="bold"),
                    content=ft.Column([ft.Text("Convert US GPA to Philippine GWA", size=12, color=subtext_color), inp, result], tight=True, spacing=12),
                    actions=[ft.TextButton("Close", on_click=lambda _: close_dialog()),
                             ft.ElevatedButton("Convert", bgcolor=accent_dark, color="white", on_click=convert)]))

            def show_gwa_to_gpa_dialog(e):
                inp = ft.TextField(label="Enter Philippine GWA (1.0 – 5.0)", border_radius=12, keyboard_type=ft.KeyboardType.NUMBER, color=text_color)
                result = ft.Text("", color=accent, size=16, weight="bold")
                def convert(e2):
                    try:
                        val = float(inp.value)
                        result.value = "⚠ GWA must be between 1.0 and 5.0" if not 1.0 <= val <= 5.0 else f"US GPA ≈ {gwa_to_gpa(val):.2f}"
                    except ValueError:
                        result.value = "⚠ Invalid number"
                    page.update()
                show_dialog(ft.AlertDialog(modal=True, title=ft.Text("GWA → GPA", weight="bold"),
                    content=ft.Column([ft.Text("Convert Philippine GWA to US GPA", size=12, color=subtext_color), inp, result], tight=True, spacing=12),
                    actions=[ft.TextButton("Close", on_click=lambda _: close_dialog()),
                             ft.ElevatedButton("Convert", bgcolor=accent_dark, color="white", on_click=convert)]))

            def show_gwa_to_pct_dialog(e):
                inp = ft.TextField(label="Enter Philippine GWA (1.0 – 5.0)", border_radius=12, keyboard_type=ft.KeyboardType.NUMBER, color=text_color)
                result = ft.Text("", color=accent, size=16, weight="bold")
                if gwa_result_val[0] > 0:
                    inp.value = f"{gwa_result_val[0]:.2f}"
                def convert(e2):
                    try:
                        val = float(inp.value)
                        result.value = "⚠ GWA must be between 1.0 and 5.0" if not 1.0 <= val <= 5.0 else f"≈ {gwa_to_percent(val)}%"
                    except ValueError:
                        result.value = "⚠ Invalid number"
                    page.update()
                show_dialog(ft.AlertDialog(modal=True, title=ft.Text("GWA → Percentage", weight="bold"),
                    content=ft.Column([ft.Text("Convert Philippine GWA to percentage grade", size=12, color=subtext_color), inp, result], tight=True, spacing=12),
                    actions=[ft.TextButton("Close", on_click=lambda _: close_dialog()),
                             ft.ElevatedButton("Convert", bgcolor=accent_dark, color="white", on_click=convert)]))

            def conv_btn(label, handler):
                return ft.ElevatedButton(label, bgcolor="#22d3ee22", color=accent,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, "#22d3ee55")),
                    on_click=handler)

            rows_container.controls += [make_row(), make_row()]
            load_history()

            content.controls = [
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: navigate_to("profile"), icon_color=text_color),
                    ft.Text("GWA Calculator", size=22, font_family="Outfit", weight="bold", color=text_color),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text("Subject", expand=2, weight="bold", text_align=ft.TextAlign.CENTER, size=13, color=subtext_color),
                    ft.Text("Units",   expand=1, weight="bold", text_align=ft.TextAlign.CENTER, size=13, color=subtext_color),
                    ft.Text("Grade",   expand=1, weight="bold", text_align=ft.TextAlign.CENTER, size=13, color=subtext_color),
                    ft.Text("", width=40),
                ]),
                ft.Divider(height=1, color=border_color),
                rows_container,
                ft.Divider(height=1, color=border_color),
                ft.Row([
                    ft.ElevatedButton("＋ Add Subject", bgcolor=row_bg, color=accent,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=add_row),
                    ft.ElevatedButton("Calculate", bgcolor=accent_dark, color="white",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=calculate_gwa),
                    ft.ElevatedButton("Reset", bgcolor=row_bg, color=subtext_color,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=reset_calc),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(bgcolor=row_bg, border_radius=14, padding=16,
                    content=ft.Row([ft.Icon(ft.Icons.SCHOOL_OUTLINED, color=accent), gwa_display], spacing=12)),
                ft.Row([conv_btn("GPA → GWA", show_gpa_to_gwa_dialog),
                        conv_btn("GWA → GPA", show_gwa_to_gpa_dialog),
                        conv_btn("GWA → %",   show_gwa_to_pct_dialog)],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                ft.Divider(height=1, color=border_color),
                ft.Row([
                    ft.Row([ft.Icon(ft.Icons.HISTORY, color=accent, size=18),
                            ft.Text("Calculation History", size=14, weight="bold", color=text_color)], spacing=6),
                    ft.TextButton("Clear All", style=ft.ButtonStyle(color="red400"), on_click=lambda _: clear_all_history()),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                history_col,
            ]

        # ─────────────────────────────────────────
        # NOTES
        # ─────────────────────────────────────────
        elif view_name == "notes":
            notes_col = ft.Column(scroll=ft.ScrollMode.AUTO, height=520, spacing=8)
            search_query = [""]

            def fmt_date(ds: str) -> str:
                if not ds: return ""
                try:
                    dt = datetime.fromisoformat(ds)
                    now = datetime.now()
                    if dt.date() == now.date():       return dt.strftime("%I:%M %p").lstrip("0")
                    elif (now - dt).days < 7:         return dt.strftime("%A")
                    else:                             return dt.strftime("%m/%d/%y")
                except Exception:                    return ds[:10]

            def load_notes(query=""):
                notes_col.controls.clear()
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                if query:
                    c.execute("SELECT id, title, content, modified FROM notes WHERE user_id=? AND (title LIKE ? OR content LIKE ?) ORDER BY modified DESC, id DESC",
                              (current_user[0], f"%{query}%", f"%{query}%"))
                else:
                    c.execute("SELECT id, title, content, modified FROM notes WHERE user_id=? ORDER BY modified DESC, id DESC", (current_user[0],))
                rows = c.fetchall(); conn.close()
                if not rows:
                    notes_col.controls.append(ft.Container(padding=40,
                        content=ft.Column([ft.Icon(ft.Icons.STICKY_NOTE_2_OUTLINED, size=48, color=subtext_color),
                                           ft.Text("No notes yet", color=subtext_color, size=15)],
                                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        alignment=ft.Alignment(0, 0)))
                else:
                    for r in rows:
                        nid, ntitle, ncontent, nmod = r
                        preview = (ncontent or "")[:60].replace("\n", " ")
                        if len(ncontent or "") > 60: preview += "…"
                        notes_col.controls.append(
                            ft.Container(bgcolor=row_bg, padding=ft.padding.symmetric(horizontal=16, vertical=14),
                                border_radius=14, border=ft.border.all(1, border_color),
                                on_click=lambda e, nid=nid, nt=ntitle, nc=ncontent: open_note_editor(nid, nt, nc),
                                content=ft.Row([
                                    ft.Column([
                                        ft.Text(ntitle or "Untitled", weight="bold", size=15, color=text_color, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Row([ft.Text(fmt_date(nmod), size=12, color=accent),
                                                ft.Text(preview, size=12, color=subtext_color, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=8),
                                    ], expand=True, spacing=4),
                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", icon_size=20,
                                                  on_click=lambda e, nid=nid: del_note(nid)),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))
                page.update()

            def open_note_editor(nid, title, content_txt):
                is_new = (nid is None)
                title_field = ft.TextField(value=title or "", hint_text="Title", border=ft.InputBorder.NONE,
                    text_style=ft.TextStyle(size=22, weight=ft.FontWeight.BOLD, color=text_color, font_family="Outfit"),
                    color=text_color, cursor_color=accent)
                body_field = ft.TextField(value=content_txt or "", hint_text="Start writing…", multiline=True,
                    min_lines=20, border=ft.InputBorder.NONE,
                    text_style=ft.TextStyle(size=15, color=text_color, height=1.6),
                    color=text_color, cursor_color=accent, expand=True)

                def save_note(e):
                    now_str = datetime.now().isoformat()
                    conn = sqlite3.connect("users.db"); c = conn.cursor()
                    if is_new:
                        c.execute("INSERT INTO notes (user_id, title, content, date, modified) VALUES (?,?,?,?,?)",
                                  (current_user[0], title_field.value, body_field.value, now_str, now_str))
                    else:
                        c.execute("UPDATE notes SET title=?, content=?, modified=? WHERE id=?",
                                  (title_field.value, body_field.value, now_str, nid))
                    conn.commit(); conn.close(); close_dialog(); load_notes(search_query[0])

                def delete_from_editor(e):
                    close_dialog()
                    if not is_new: del_note(nid)

                show_dialog(ft.AlertDialog(modal=True,
                    title=ft.Row([ft.Text("Note" if is_new else "Edit Note", weight="bold", color=text_color),
                                  ft.Row([ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", icon_size=20,
                                                        on_click=delete_from_editor, visible=not is_new),
                                          ft.IconButton(ft.Icons.CHECK, icon_color=accent, icon_size=22, on_click=save_note)])],
                                 alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    content=ft.Container(width=400, height=460,
                        content=ft.Column([title_field, ft.Divider(height=1, color=border_color),
                                           ft.Text(datetime.now().strftime("%d %B %Y at %I:%M %p").lstrip("0"), size=11, color=subtext_color),
                                           body_field], spacing=6, scroll=ft.ScrollMode.AUTO)),
                    actions=[ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
                             ft.ElevatedButton("Done", bgcolor=accent_dark, color="white",
                                 style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=save_note)],
                    actions_padding=ft.padding.symmetric(horizontal=16, vertical=8)))

            def add_note(e): open_note_editor(None, "", "")

            def del_note(nid):
                def confirm(e):
                    conn = sqlite3.connect("users.db"); c = conn.cursor()
                    c.execute("DELETE FROM notes WHERE id=?", (nid,))
                    conn.commit(); conn.close(); close_dialog(); load_notes(search_query[0])
                show_dialog(ft.AlertDialog(modal=True, title=ft.Text("Delete Note"),
                    content=ft.Text("Are you sure you want to delete this note?"),
                    actions=[ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
                             ft.TextButton("Delete", style=ft.ButtonStyle(color="red"), on_click=confirm)]))

            def on_search_change(e):
                search_query[0] = e.control.value; load_notes(search_query[0])

            search_field = ft.TextField(hint_text="Search notes…", prefix_icon=ft.Icons.SEARCH,
                border_radius=14, on_change=on_search_change, bgcolor=row_bg, color=text_color, height=46)
            load_notes()
            content.controls = [
                ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: navigate_to("profile"), icon_color=text_color),
                        ft.Text("Notes", size=24, font_family="Outfit", weight="bold", color=text_color)],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                search_field, notes_col,
                ft.Row([ft.FloatingActionButton(icon=ft.Icons.EDIT_OUTLINED, bgcolor=accent_dark,
                    foreground_color="white", on_click=add_note, mini=True)], alignment=ft.MainAxisAlignment.CENTER),
            ]

        # ─────────────────────────────────────────
        # CLASS SCHEDULE  (full scheduling system)
        # ─────────────────────────────────────────
        elif view_name == "class_schedule":

            # ── DB helpers ──
            def db_get_teachers():
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("SELECT teacher_id, teacher_name FROM sched_teachers ORDER BY teacher_name")
                r = c.fetchall(); conn.close(); return r

            def db_get_subjects():
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("SELECT subject_id, subject_code, subject_title FROM sched_subjects ORDER BY subject_code")
                r = c.fetchall(); conn.close(); return r

            def db_get_rooms():
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("SELECT room_id, room_name FROM sched_rooms ORDER BY room_name")
                r = c.fetchall(); conn.close(); return r

            def db_get_schedules():
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("""
                    SELECT s.schedule_id, t.teacher_name, sub.subject_code, sub.subject_title,
                           r.room_name, s.day, s.start_time, s.end_time,
                           s.teacher_id, s.subject_id, s.room_id
                    FROM sched_schedules s
                    JOIN sched_teachers t  ON s.teacher_id = t.teacher_id
                    JOIN sched_subjects sub ON s.subject_id = sub.subject_id
                    JOIN sched_rooms r     ON s.room_id    = r.room_id
                    ORDER BY s.day, s.start_time
                """)
                r = c.fetchall(); conn.close(); return r

            def db_check_conflict(room_id, teacher_id, day, start, end, exclude_id=None):
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                q = "SELECT * FROM sched_schedules WHERE room_id=? AND day=? AND start_time < ? AND end_time > ?"
                p = [room_id, day, end, start]
                if exclude_id: q += " AND schedule_id != ?"; p.append(exclude_id)
                c.execute(q, p)
                if c.fetchone(): conn.close(); return "Room is already occupied during this time."
                q = "SELECT * FROM sched_schedules WHERE teacher_id=? AND day=? AND start_time < ? AND end_time > ?"
                p = [teacher_id, day, end, start]
                if exclude_id: q += " AND schedule_id != ?"; p.append(exclude_id)
                c.execute(q, p)
                if c.fetchone(): conn.close(); return "Teacher already has a class during this time."
                conn.close(); return None

            def db_add_schedule(teacher_id, subject_id, room_id, day, start, end):
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("INSERT INTO sched_schedules (teacher_id,subject_id,room_id,day,start_time,end_time) VALUES (?,?,?,?,?,?)",
                          (teacher_id, subject_id, room_id, day, start, end))
                conn.commit(); conn.close()

            def db_update_schedule(sid, teacher_id, subject_id, room_id, day, start, end):
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("UPDATE sched_schedules SET teacher_id=?,subject_id=?,room_id=?,day=?,start_time=?,end_time=? WHERE schedule_id=?",
                          (teacher_id, subject_id, room_id, day, start, end, sid))
                conn.commit(); conn.close()

            def db_delete_schedule(sid):
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("DELETE FROM sched_schedules WHERE schedule_id=?", (sid,))
                conn.commit(); conn.close()

            # ── Manage entity dialogs ──
            def open_manage_dialog(entity_type):
                """Generic manage dialog for teachers, subjects, rooms."""
                list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=280)
                inp1 = ft.TextField(color=text_color, bgcolor="#1a1f35", border_radius=10, text_size=13, expand=True)
                inp2 = ft.TextField(color=text_color, bgcolor="#1a1f35", border_radius=10, text_size=13, expand=True)
                msg  = ft.Text("", color="red400", size=12)

                if entity_type == "teachers":
                    inp1.label = "Teacher Name"; inp2.visible = False
                elif entity_type == "subjects":
                    inp1.label = "Subject Code"; inp2.label = "Subject Title"
                else:
                    inp1.label = "Room Name"; inp2.visible = False

                def refresh_list():
                    list_col.controls.clear()
                    if entity_type == "teachers":
                        items = db_get_teachers()
                        for item in items:
                            iid, iname = item
                            list_col.controls.append(
                                ft.Container(bgcolor=row_bg, border_radius=10, padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                    content=ft.Row([ft.Text(iname, color=text_color, size=13, expand=True),
                                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", icon_size=16,
                                                                  on_click=lambda e, i=iid: delete_entity("teachers", i))],
                                                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))
                    elif entity_type == "subjects":
                        items = db_get_subjects()
                        for item in items:
                            iid, icode, ititle = item
                            list_col.controls.append(
                                ft.Container(bgcolor=row_bg, border_radius=10, padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                    content=ft.Row([ft.Column([ft.Text(icode, color=accent, size=12, weight="bold"),
                                                               ft.Text(ititle, color=text_color, size=12)], spacing=2, expand=True),
                                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", icon_size=16,
                                                                  on_click=lambda e, i=iid: delete_entity("subjects", i))],
                                                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))
                    else:
                        items = db_get_rooms()
                        for item in items:
                            iid, iname = item
                            list_col.controls.append(
                                ft.Container(bgcolor=row_bg, border_radius=10, padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                    content=ft.Row([ft.Text(iname, color=text_color, size=13, expand=True),
                                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", icon_size=16,
                                                                  on_click=lambda e, i=iid: delete_entity("rooms", i))],
                                                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))
                    page.update()

                def delete_entity(etype, eid):
                    conn = sqlite3.connect("users.db"); c = conn.cursor()
                    tbl = {"teachers": "sched_teachers", "subjects": "sched_subjects", "rooms": "sched_rooms"}
                    pk  = {"teachers": "teacher_id",     "subjects": "subject_id",     "rooms": "room_id"}
                    c.execute(f"DELETE FROM {tbl[etype]} WHERE {pk[etype]}=?", (eid,))
                    conn.commit(); conn.close(); refresh_list()

                def add_entity(e):
                    if not inp1.value:
                        msg.value = "Name/Code is required!"; page.update(); return
                    conn = sqlite3.connect("users.db"); c = conn.cursor()
                    if entity_type == "teachers":
                        c.execute("INSERT INTO sched_teachers (teacher_name) VALUES (?)", (inp1.value,))
                    elif entity_type == "subjects":
                        if not inp2.value:
                            msg.value = "Subject title is required!"; conn.close(); page.update(); return
                        c.execute("INSERT INTO sched_subjects (subject_code, subject_title) VALUES (?,?)", (inp1.value, inp2.value))
                    else:
                        c.execute("INSERT INTO sched_rooms (room_name) VALUES (?)", (inp1.value,))
                    conn.commit(); conn.close()
                    inp1.value = ""; inp2.value = ""; msg.value = ""
                    refresh_list()

                refresh_list()
                title_map = {"teachers": "Manage Teachers", "subjects": "Manage Subjects", "rooms": "Manage Rooms"}
                show_dialog(ft.AlertDialog(
                    modal=True, bgcolor="#0d111e",
                    title=ft.Text(title_map[entity_type], weight="bold", color=text_color),
                    content=ft.Container(width=360,
                        content=ft.Column([
                            ft.Row([inp1, inp2] if entity_type == "subjects" else [inp1], spacing=8),
                            msg,
                            ft.ElevatedButton("Add", bgcolor=accent_dark, color="white",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=add_entity),
                            ft.Divider(color=border_color),
                            ft.Text("Existing entries:", size=12, color=subtext_color),
                            list_col,
                        ], spacing=8, tight=True)),
                    actions=[ft.TextButton("Close", on_click=lambda _: (close_dialog(), refresh_schedule_table()))],
                ))

            # ── Schedule table ──
            sched_table_col = ft.Column(spacing=0)
            sched_msg = ft.Text("", size=13, color="red400")

            # Form state for editing
            edit_state = {"id": None}

            def build_form_dropdowns():
                teachers = db_get_teachers()
                subjects = db_get_subjects()
                rooms    = db_get_rooms()
                t_dd = ft.Dropdown(label="Teacher", border_radius=10, color=text_color, bgcolor="#1a1f35",
                    label_style=ft.TextStyle(color=subtext_color, size=12), text_size=13,
                    options=[ft.dropdown.Option(str(t[0]), t[1]) for t in teachers])
                s_dd = ft.Dropdown(label="Subject", border_radius=10, color=text_color, bgcolor="#1a1f35",
                    label_style=ft.TextStyle(color=subtext_color, size=12), text_size=13,
                    options=[ft.dropdown.Option(str(s[0]), f"{s[1]} – {s[2]}") for s in subjects])
                r_dd = ft.Dropdown(label="Room", border_radius=10, color=text_color, bgcolor="#1a1f35",
                    label_style=ft.TextStyle(color=subtext_color, size=12), text_size=13,
                    options=[ft.dropdown.Option(str(r[0]), r[1]) for r in rooms])
                day_dd = ft.Dropdown(label="Day", border_radius=10, color=text_color, bgcolor="#1a1f35",
                    label_style=ft.TextStyle(color=subtext_color, size=12), text_size=13, width=130,
                    options=[ft.dropdown.Option(d) for d in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]])
                st_f = ft.TextField(label="Start (e.g. 07:30)", border_radius=10, color=text_color,
                    bgcolor="#1a1f35", label_style=ft.TextStyle(color=subtext_color, size=12), text_size=13, width=140)
                et_f = ft.TextField(label="End   (e.g. 09:00)", border_radius=10, color=text_color,
                    bgcolor="#1a1f35", label_style=ft.TextStyle(color=subtext_color, size=12), text_size=13, width=140)
                return t_dd, s_dd, r_dd, day_dd, st_f, et_f

            # Build form once; we'll rebuild on refresh
            form_refs = [None]  # mutable holder

            def open_schedule_form(edit_rec=None):
                is_edit = edit_rec is not None
                t_dd, s_dd, r_dd, day_dd, st_f, et_f = build_form_dropdowns()

                if is_edit:
                    t_dd.value   = str(edit_rec[8])
                    s_dd.value   = str(edit_rec[9])
                    r_dd.value   = str(edit_rec[10])
                    day_dd.value = edit_rec[5]
                    st_f.value   = edit_rec[6]
                    et_f.value   = edit_rec[7]

                dlg_msg = ft.Text("", color="red400", size=12)

                def save(e):
                    if not all([t_dd.value, s_dd.value, r_dd.value, day_dd.value, st_f.value, et_f.value]):
                        dlg_msg.value = "All fields are required!"; page.update(); return
                    conflict = db_check_conflict(r_dd.value, t_dd.value, day_dd.value,
                                                 st_f.value, et_f.value,
                                                 exclude_id=edit_rec[0] if is_edit else None)
                    if conflict:
                        dlg_msg.value = conflict; page.update(); return
                    if is_edit:
                        db_update_schedule(edit_rec[0], t_dd.value, s_dd.value, r_dd.value,
                                           day_dd.value, st_f.value, et_f.value)
                    else:
                        db_add_schedule(t_dd.value, s_dd.value, r_dd.value,
                                        day_dd.value, st_f.value, et_f.value)
                    close_dialog()
                    refresh_schedule_table()

                show_dialog(ft.AlertDialog(
                    modal=True, bgcolor="#0d111e",
                    title=ft.Container(
                        content=ft.Row([
                            ft.Container(width=4, height=28, border_radius=4, bgcolor=accent),
                            ft.Text("Edit Schedule" if is_edit else "Add Schedule", size=18, weight="bold", color=text_color),
                        ], spacing=10), padding=ft.padding.only(bottom=4)),
                    content=ft.Container(width=370, padding=ft.padding.only(top=4),
                        content=ft.Column([
                            ft.Text("ASSIGN", size=11, weight="bold", color=subtext_color),
                            t_dd, s_dd, r_dd,
                            ft.Divider(height=1, color="#ffffff10"),
                            ft.Text("SCHEDULE", size=11, weight="bold", color=subtext_color),
                            ft.Row([day_dd, st_f, et_f], spacing=8),
                            dlg_msg,
                        ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO)),
                    actions=[
                        ft.TextButton("Cancel", style=ft.ButtonStyle(color=subtext_color), on_click=lambda _: close_dialog()),
                        ft.ElevatedButton("Update" if is_edit else "Add", bgcolor=accent_dark, color="white",
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=save),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                ))

            def delete_sched_record(sid):
                def confirm(e):
                    db_delete_schedule(sid); close_dialog(); refresh_schedule_table()
                show_dialog(ft.AlertDialog(modal=True, title=ft.Text("Delete Schedule"),
                    content=ft.Text("Remove this schedule entry?"),
                    actions=[ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
                             ft.TextButton("Delete", style=ft.ButtonStyle(color="red"), on_click=confirm)]))

            # ── DAY colors ──
            DAY_COLORS = {
                "Monday": "#3b82f6", "Tuesday": "#8b5cf6", "Wednesday": "#22d3ee",
                "Thursday": "#f59e0b", "Friday": "#10b981", "Saturday": "#f43f5e",
            }

            def refresh_schedule_table():
                sched_table_col.controls.clear()
                schedules = db_get_schedules()

                def hcell(txt, flex=1):
                    return ft.Container(expand=flex,
                        content=ft.Text(txt, size=10, weight="bold", color=subtext_color),
                        padding=ft.padding.symmetric(horizontal=6, vertical=10))

                sched_table_col.controls.append(
                    ft.Container(bgcolor="#0a0e1a",
                        border_radius=ft.border_radius.only(top_left=12, top_right=12),
                        content=ft.Row([
                            hcell("DAY",     2), hcell("TEACHER", 3), hcell("SUBJECT",  3),
                            hcell("ROOM",    3), hcell("TIME",    3), hcell("",         2),
                        ], spacing=0),
                        border=ft.border.only(bottom=ft.BorderSide(1, border_color))))

                if not schedules:
                    sched_table_col.controls.append(
                        ft.Container(bgcolor=row_bg,
                            border_radius=ft.border_radius.only(bottom_left=12, bottom_right=12),
                            padding=40,
                            content=ft.Column([
                                ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED, size=40, color=subtext_color),
                                ft.Text("No schedules yet. Add one!", color=subtext_color, size=13),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                            alignment=ft.Alignment(0, 0)))
                else:
                    for i, s in enumerate(schedules):
                        is_last = (i == len(schedules) - 1)
                        sid, teacher, scode, stitle, room, day, start, end = s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7]
                        day_col = DAY_COLORS.get(day, accent)

                        def dcell(txt, flex=1, col=None, bold=False):
                            return ft.Container(expand=flex,
                                content=ft.Text(str(txt) if txt else "—", size=11,
                                    weight="bold" if bold else "normal",
                                    color=col or text_color, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                padding=ft.padding.symmetric(horizontal=6, vertical=10))

                        sched_table_col.controls.append(
                            ft.Container(
                                bgcolor=row_bg if i % 2 == 0 else "#121627",
                                border_radius=ft.border_radius.only(
                                    bottom_left=12 if is_last else 0,
                                    bottom_right=12 if is_last else 0),
                                border=ft.border.only(bottom=ft.BorderSide(1, border_color)) if not is_last else None,
                                content=ft.Row([
                                    dcell(day,     2, col=day_col,      bold=True),
                                    dcell(teacher, 3),
                                    dcell(scode,   3, col=accent,       bold=True),
                                    dcell(room,    3, col=subtext_color),
                                    dcell(f"{start}–{end}", 3),
                                    ft.Container(expand=2, content=ft.Row([
                                        ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_color="blue400", icon_size=16,
                                            tooltip="Edit", on_click=lambda e, rec=s: open_schedule_form(rec)),
                                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", icon_size=16,
                                            tooltip="Delete", on_click=lambda e, s_id=sid: delete_sched_record(s_id)),
                                    ], spacing=0)),
                                ], spacing=0)))
                page.update()

            refresh_schedule_table()

            # ── Manage buttons row ──
            def mgr_btn(label, icon, etype):
                return ft.Container(
                    expand=True, height=44, border_radius=10,
                    bgcolor="#22d3ee11",
                    border=ft.border.all(1, "#22d3ee33"),
                    on_click=lambda _, et=etype: open_manage_dialog(et),
                    content=ft.Row([ft.Icon(icon, color=accent, size=14),
                                    ft.Text(label, size=12, color=accent, weight="w600")],
                                   alignment=ft.MainAxisAlignment.CENTER, spacing=4))

            content.controls = [
                # Header
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: navigate_to("profile"), icon_color=text_color),
                    ft.Column([
                        ft.Text("Class Schedule", size=22, font_family="Outfit", weight="bold", color=text_color),
                        ft.Text("Manage class schedules, teachers, subjects & rooms", size=11, color=subtext_color),
                    ], spacing=1, expand=True),
                ], alignment=ft.MainAxisAlignment.START, spacing=4),

                ft.Divider(height=1, color=border_color),

                # Manage entities row
                ft.Row([
                    mgr_btn("Teachers", ft.Icons.PERSON_OUTLINED,       "teachers"),
                    mgr_btn("Subjects", ft.Icons.BOOK_OUTLINED,         "subjects"),
                    mgr_btn("Rooms",    ft.Icons.MEETING_ROOM_OUTLINED,  "rooms"),
                ], spacing=8),

                ft.Divider(height=1, color=border_color),

                # Schedule table
                ft.Container(
                    content=ft.Row([ft.Container(content=sched_table_col, expand=True)], scroll=ft.ScrollMode.AUTO),
                    border_radius=14, border=ft.border.all(1, border_color),
                    clip_behavior=ft.ClipBehavior.HARD_EDGE),

                # Add schedule button
                ft.ElevatedButton(
                    "＋ Add Schedule", width=380, height=48,
                    bgcolor=accent_dark, color="white",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                    icon=ft.Icons.ADD,
                    on_click=lambda _: open_schedule_form(None)),
            ]

        # ─────────────────────────────────────────
        # ADMIN DASHBOARD
        # ─────────────────────────────────────────
        elif view_name == "admin_dashboard":
            user_list = ft.Column(scroll=ft.ScrollMode.AUTO, height=500, spacing=10)

            def load_users():
                user_list.controls.clear()
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("SELECT id, username, full_name, email, password, bio, role FROM users")
                users = c.fetchall(); conn.close()
                for u in users:
                    uid, uname, urole = u[0], u[1], u[6]
                    role_color = accent if urole == "admin" else subtext_color
                    user_list.controls.append(
                        ft.Container(bgcolor=row_bg, padding=15, border_radius=14,
                            border=ft.border.all(1, border_color),
                            content=ft.Row([
                                ft.Column([ft.Text(uname, weight="bold", color=text_color, size=15),
                                           ft.Text(urole.upper(), size=11, color=role_color, weight="w600")],
                                          expand=True, spacing=3),
                                ft.Row([
                                    ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_color="blue400", tooltip="Edit",
                                                  on_click=lambda e, ud=u: open_user_modal(ud)),
                                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color="red400",
                                                  visible=(uname != "admin"),
                                                  on_click=lambda e, uid=uid: delete_user(uid)) if uname != "admin"
                                    else ft.Icon(ft.Icons.VERIFIED, color=accent),
                                ]),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))
                page.update()

            def open_user_modal(edit_user=None):
                is_edit = edit_user is not None
                un_f  = ft.TextField(label="Username",  border_radius=12, color=text_color, value=edit_user[1] if is_edit else "")
                fn_f  = ft.TextField(label="Full Name", border_radius=12, color=text_color, value=edit_user[2] if is_edit else "")
                em_f  = ft.TextField(label="Email",     border_radius=12, color=text_color, value=edit_user[3] if is_edit else "")
                pw_f  = ft.TextField(label="Password",  border_radius=12, color=text_color,
                                     password=True, can_reveal_password=True, value=edit_user[4] if is_edit else "")
                role_dd = ft.Dropdown(label="Role", border_radius=12, value=edit_user[6] if is_edit else "user",
                    options=[ft.dropdown.Option("user"), ft.dropdown.Option("admin")])

                def save_user(e):
                    if not un_f.value or not pw_f.value:
                        show_snack("Username and Password are required!", "red700"); return
                    conn = sqlite3.connect("users.db"); c = conn.cursor()
                    try:
                        if is_edit:
                            c.execute("UPDATE users SET username=?, full_name=?, email=?, password=?, role=? WHERE id=?",
                                      (un_f.value, fn_f.value, em_f.value, pw_f.value, role_dd.value, edit_user[0]))
                        else:
                            c.execute("INSERT INTO users (username, full_name, email, password, bio, role) VALUES (?,?,?,?,?,?)",
                                      (un_f.value, fn_f.value, em_f.value, pw_f.value, "New User Profile", role_dd.value))
                        conn.commit(); close_dialog(); load_users()
                    except sqlite3.IntegrityError:
                        show_snack("Username already exists!", "red700")
                    finally:
                        conn.close()

                show_dialog(ft.AlertDialog(modal=True,
                    title=ft.Text("Edit User" if is_edit else "Add New User", weight="bold"),
                    content=ft.Column([un_f, fn_f, em_f, pw_f, role_dd], tight=True, spacing=10),
                    actions=[ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
                             ft.ElevatedButton("Update" if is_edit else "Create",
                                 bgcolor=accent_dark, color="white", on_click=save_user)]))

            def delete_user(uid):
                def confirm(e):
                    conn = sqlite3.connect("users.db"); c = conn.cursor()
                    c.execute("DELETE FROM users WHERE id=?", (uid,))
                    conn.commit(); conn.close(); close_dialog(); load_users()
                show_dialog(ft.AlertDialog(modal=True, title=ft.Text("Confirm Delete"),
                    content=ft.Text("Remove this user permanently?"),
                    actions=[ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
                             ft.TextButton("Delete", style=ft.ButtonStyle(color="red"), on_click=confirm)]))

            load_users()
            content.controls = [
                ft.Row([
                    ft.Column([ft.Text("Admin Hub", size=26, font_family="Outfit", weight="bold", color=text_color),
                               ft.Text("User Management", size=12, color=subtext_color)], spacing=2),
                    ft.IconButton(ft.Icons.LOGOUT, icon_color=subtext_color, on_click=lambda _: navigate_to("login")),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(width=380, height=52, border_radius=14, bgcolor=row_bg,
                    border=ft.border.all(1, f"{accent}44"), on_click=lambda _: open_user_modal(),
                    content=ft.Row([ft.Icon(ft.Icons.PERSON_ADD_OUTLINED, color=accent, size=20),
                                    ft.Text("Add New User", color=accent, weight="w600")],
                                   alignment=ft.MainAxisAlignment.CENTER, spacing=8)),
                ft.Divider(height=1, color=border_color),
                user_list,
            ]

        # ─────────────────────────────────────────
        # FORGOT PASSWORD / OTP
        # ─────────────────────────────────────────
        elif view_name == "forgot_password":
            em_field = ft.TextField(label="Email", border_radius=14, color=text_color,
                prefix_icon=ft.Icons.EMAIL_OUTLINED, data="fp_email", value=_r("fp_email"))
            def send_otp(e):
                global temp_otp, temp_email
                if not em_field.value: show_snack("Please enter your email.", "red700"); return
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("SELECT id FROM users WHERE email=?", (em_field.value,))
                found = c.fetchone(); conn.close()
                if not found: show_snack("Email not found.", "red700"); return
                temp_email = em_field.value; temp_otp = str(random.randint(1000, 9999))
                show_snack(f"OTP (demo): {temp_otp}"); navigate_to("otp_verification")
            content.controls = [
                ft.Text("Reset Password", size=30, font_family="Outfit", weight="bold", color=text_color),
                ft.Text("Enter your registered email address.", size=13, color=subtext_color),
                em_field,
                ft.ElevatedButton("Send OTP", width=380, height=52, bgcolor=accent_dark, color="white",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=send_otp),
                ft.TextButton("Back to Login", on_click=lambda _: navigate_to("login")),
            ]

        elif view_name == "otp_verification":
            code_field = ft.TextField(label="Enter OTP", text_align=ft.TextAlign.CENTER, border_radius=14,
                color=text_color, keyboard_type=ft.KeyboardType.NUMBER, data="otp_code", value=_r("otp_code"))
            err = ft.Text("", color="red400", size=12, visible=False)
            def verify(e):
                if code_field.value == temp_otp: navigate_to("new_password")
                else: err.value = "Incorrect OTP. Try again."; err.visible = True; page.update()
            content.controls = [
                ft.Text("Enter OTP", size=30, font_family="Outfit", weight="bold", color=text_color),
                ft.Text("Check your email for the one-time code.", size=13, color=subtext_color),
                code_field, err,
                ft.ElevatedButton("Verify", width=380, height=52, bgcolor=accent_dark, color="white",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=verify),
                ft.TextButton("Back", on_click=lambda _: navigate_to("forgot_password")),
            ]

        elif view_name == "new_password":
            p1 = ft.TextField(label="New Password",     password=True, can_reveal_password=True, border_radius=14, color=text_color)
            p2 = ft.TextField(label="Confirm Password", password=True, can_reveal_password=True, border_radius=14, color=text_color)
            err = ft.Text("", color="red400", size=12, visible=False)
            def update_password(e):
                if not p1.value: err.value = "Password cannot be empty."; err.visible = True; page.update(); return
                if p1.value != p2.value: err.value = "Passwords do not match."; err.visible = True; page.update(); return
                conn = sqlite3.connect("users.db"); c = conn.cursor()
                c.execute("UPDATE users SET password=? WHERE email=?", (p1.value, temp_email))
                conn.commit(); conn.close(); show_snack("Password updated! Please log in."); navigate_to("login")
            content.controls = [
                ft.Text("New Password", size=30, font_family="Outfit", weight="bold", color=text_color),
                p1, p2, err,
                ft.ElevatedButton("Update Password", width=380, height=52, bgcolor=accent_dark, color="white",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=update_password),
            ]

        # ── Wrap in centered card ──────────────────────────
        card = ft.Container(
            width=420,
            padding=ft.padding.symmetric(horizontal=22, vertical=24),
            border_radius=28,
            bgcolor=card_color,
            border=ft.border.all(1, border_color),
            shadow=ft.BoxShadow(blur_radius=60, spread_radius=2, color=shadow_color),
            content=content,
        )

        page.add(card)

    navigate_to("login")


if __name__ == "__main__":
    ft.app(target=main)