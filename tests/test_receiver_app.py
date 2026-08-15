"""Small GUI helper tests that do not require creating a Tk window."""
from sqr.receiver.app import ReceiverApp


class _Var:
    def __init__(self, value):
        self.value = value

    def set(self, value):
        self.value = value


class _Dialog:
    def __init__(self, directory):
        self.directory = directory
        self.title = None

    def askdirectory(self, title):
        self.title = title
        return self.directory


def _app_for_directory_picker(selected, initial="sqr_output.txt"):
    app = ReceiverApp.__new__(ReceiverApp)
    app._filedialog = _Dialog(selected)
    app.output_var = _Var(initial)
    app.logged = []
    app._log = app.logged.append
    return app


def test_browse_output_directory_sets_parent_path_and_logs():
    app = _app_for_directory_picker("/tmp/restored-parent")

    app._browse_output_directory()

    assert app.output_var.value == "/tmp/restored-parent"
    assert "保存父目录" in app._filedialog.title
    assert app.logged == ["目录包将还原到父目录 → /tmp/restored-parent"]


def test_browse_output_directory_cancel_keeps_existing_value():
    app = _app_for_directory_picker("", initial="existing.txt")

    app._browse_output_directory()

    assert app.output_var.value == "existing.txt"
    assert app.logged == []
