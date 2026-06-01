
from model import (
    AppState,
    UserModel,
    GradeModel,
    GwaHistoryModel,
    NotesModel,
    ScheduleModel,
    generate_otp,
    gwa_to_gpa,
    gpa_to_gwa,
    gwa_to_percent,
    get_school_years,
)


class AppController:
    """
    One controller instance is created inside main() and passed to the View.
    The View calls controller methods on user interaction; the controller
    updates the Model and instructs the View what to display next.
    """

    def __init__(self, navigate_cb, snack_cb):
        """
        Parameters
        ----------
        navigate_cb : callable(view_name: str)
            Asks the View to render a named screen.
        snack_cb : callable(msg: str, color: str)
            Asks the View to show a snack-bar notification.
        """
        self._navigate = navigate_cb
        self._snack    = snack_cb
        self.state     = AppState()

    # ════════════════════════════════════════════════════════════════════════
    # NAVIGATION
    # ════════════════════════════════════════════════════════════════════════

    def navigate_to(self, view_name: str) -> None:
        if view_name != self.state.current_view:
            self.state.form_state = {}
        self.state.current_view = view_name
        self._navigate(view_name)

    # ════════════════════════════════════════════════════════════════════════
    # AUTH
    # ════════════════════════════════════════════════════════════════════════

    def login(self, username: str, password: str) -> bool:
        """Returns True and navigates on success; returns False on failure."""
        row = UserModel.authenticate(username, password)
        if row:
            self.state.current_user = row
            dest = "admin_dashboard" if row[6] == "admin" else "profile"
            self.navigate_to(dest)
            return True
        return False

    def register(self, username: str, full_name: str,
                 email: str, password: str) -> bool:
        if not username or not password:
            self._snack("Username and Password are required!", "red700")
            return False
        ok = UserModel.register(username, full_name, email, password)
        if ok:
            self._snack("Account created! Please log in.")
            self.navigate_to("login")
        else:
            self._snack("Username already exists!", "red700")
        return ok

    def logout(self) -> None:
        self.state.current_user = None
        self.state.form_state   = {}
        self.navigate_to("login")

    # ── Forgot password flow ────────────────────────────────────────────────

    def request_otp(self, email: str) -> bool:
        if not email:
            self._snack("Please enter your email.", "red700")
            return False
        row = UserModel.find_by_email(email)
        if not row:
            self._snack("Email not found.", "red700")
            return False
        self.state.temp_email = email
        self.state.temp_otp   = generate_otp()
        self._snack(f"OTP (demo): {self.state.temp_otp}")
        self.navigate_to("otp_verification")
        return True

    def verify_otp(self, code: str) -> bool:
        if code == self.state.temp_otp:
            self.navigate_to("new_password")
            return True
        return False

    def update_password(self, password: str, confirm: str) -> bool:
        if not password:
            self._snack("Password cannot be empty.", "red700")
            return False
        if password != confirm:
            self._snack("Passwords do not match.", "red700")
            return False
        UserModel.update_password(self.state.temp_email, password)
        self._snack("Password updated! Please log in.")
        self.navigate_to("login")
        return True

    # ════════════════════════════════════════════════════════════════════════
    # ADMIN — USER MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════

    def get_all_users(self) -> list[tuple]:
        return UserModel.get_all()

    def admin_create_user(self, username: str, full_name: str,
                          email: str, password: str, role: str) -> bool:
        if not username or not password:
            self._snack("Username and Password are required!", "red700")
            return False
        ok = UserModel.create(username, full_name, email, password, role)
        if not ok:
            self._snack("Username already exists!", "red700")
        return ok

    def admin_update_user(self, uid: int, username: str, full_name: str,
                          email: str, password: str, role: str) -> bool:
        if not username or not password:
            self._snack("Username and Password are required!", "red700")
            return False
        ok = UserModel.update(uid, username, full_name, email, password, role)
        if not ok:
            self._snack("Username already exists!", "red700")
        return ok

    def admin_delete_user(self, uid: int) -> None:
        UserModel.delete(uid)

    # ════════════════════════════════════════════════════════════════════════
    # GRADES
    # ════════════════════════════════════════════════════════════════════════

    def get_grades(self, school_year: str, semester: str) -> list[tuple]:
        return GradeModel.fetch(
            self.state.current_user[0], school_year, semester
        )

    def compute_gwa(self, records: list[tuple]) -> tuple[float, float | None]:
        return GradeModel.compute_gwa(records)

    def add_grade(self, school_year: str, semester: str,
                  code: str, title: str, units: float,
                  grade: str, status: str, remarks: str, faculty: str) -> None:
        GradeModel.insert(
            self.state.current_user[0], school_year, semester,
            code, title, units, grade, status, remarks, faculty,
        )

    def update_grade(self, rid: int, code: str, title: str, units: float,
                     grade: str, status: str, remarks: str, faculty: str) -> None:
        GradeModel.update(rid, code, title, units, grade, status, remarks, faculty)

    def delete_grade(self, rid: int) -> None:
        GradeModel.delete(rid)

    def clear_semester(self, school_year: str, semester: str) -> None:
        GradeModel.delete_semester(
            self.state.current_user[0], school_year, semester
        )

    # ── Conversion helpers (delegated to Model) ─────────────────────────────

    def gwa_to_gpa(self, gwa: float) -> float:
        return gwa_to_gpa(gwa)

    def gpa_to_gwa(self, gpa: float) -> float:
        return gpa_to_gwa(gpa)

    def gwa_to_percent(self, gwa: float) -> float:
        return gwa_to_percent(gwa)

    def get_school_years(self) -> list[str]:
        return get_school_years()

    # ════════════════════════════════════════════════════════════════════════
    # GWA HISTORY
    # ════════════════════════════════════════════════════════════════════════

    def get_gwa_history(self) -> list[tuple]:
        return GwaHistoryModel.fetch(self.state.current_user[0])

    def save_gwa_calculation(self, gwa: float, subjects_str: str) -> None:
        GwaHistoryModel.insert(self.state.current_user[0], gwa, subjects_str)

    def delete_gwa_history(self, hid: int) -> None:
        GwaHistoryModel.delete(hid)

    def clear_gwa_history(self) -> None:
        GwaHistoryModel.clear(self.state.current_user[0])

    # ════════════════════════════════════════════════════════════════════════
    # NOTES
    # ════════════════════════════════════════════════════════════════════════

    def get_notes(self, query: str = "") -> list[tuple]:
        return NotesModel.fetch(self.state.current_user[0], query)

    def add_note(self, title: str, content: str) -> None:
        NotesModel.insert(self.state.current_user[0], title, content)

    def update_note(self, nid: int, title: str, content: str) -> None:
        NotesModel.update(nid, title, content)

    def delete_note(self, nid: int) -> None:
        NotesModel.delete(nid)

    # ════════════════════════════════════════════════════════════════════════
    # SCHEDULING
    # ════════════════════════════════════════════════════════════════════════

    def get_teachers(self):   return ScheduleModel.get_teachers()
    def get_subjects(self):   return ScheduleModel.get_subjects()
    def get_rooms(self):      return ScheduleModel.get_rooms()
    def get_schedules(self):  return ScheduleModel.get_schedules()

    def add_schedule(self, teacher_id, subject_id, room_id,
                     day, start, end) -> str | None:
        """Returns a conflict error message or None on success."""
        conflict = ScheduleModel.check_conflict(room_id, teacher_id, day, start, end)
        if conflict:
            return conflict
        ScheduleModel.add_schedule(teacher_id, subject_id, room_id, day, start, end)
        return None

    def update_schedule(self, sid, teacher_id, subject_id, room_id,
                        day, start, end) -> str | None:
        conflict = ScheduleModel.check_conflict(
            room_id, teacher_id, day, start, end, exclude_id=sid
        )
        if conflict:
            return conflict
        ScheduleModel.update_schedule(sid, teacher_id, subject_id, room_id, day, start, end)
        return None

    def delete_schedule(self, sid) -> None:
        ScheduleModel.delete_schedule(sid)

    def add_teacher(self, name: str) -> bool:
        if not name:
            return False
        ScheduleModel.add_teacher(name)
        return True

    def add_subject(self, code: str, title: str) -> bool:
        if not code or not title:
            return False
        ScheduleModel.add_subject(code, title)
        return True

    def add_room(self, name: str) -> bool:
        if not name:
            return False
        ScheduleModel.add_room(name)
        return True

    def delete_entity(self, entity_type: str, eid: int) -> None:
        ScheduleModel.delete_entity(entity_type, eid)
