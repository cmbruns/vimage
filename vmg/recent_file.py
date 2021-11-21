import os
from PySide6 import QtCore, QtGui, QtWidgets


class RecentFile(QtGui.QAction):
    """QAction that reopens a previously opened file"""

    def __init__(self, file_name, open_file_slot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_name = file_name
        self.triggered.connect(self.on_triggered)
        self.open_file_requested.connect(open_file_slot)
        self.setText(file_name)

    def __eq__(self, rhs):
        return self.file_name == str(rhs)

    def __str__(self) -> str:
        return self.file_name

    open_file_requested = QtCore.Signal(str)
    file_not_found = QtCore.Signal(str)

    @QtCore.Slot()
    def on_triggered(self):
        if os.path.exists(self.file_name):
            self.open_file_requested.emit(self.file_name)
        else:
            print("recent file not found")
            self.file_not_found.emit(self.file_name)


class RecentFileList(QtCore.QObject):
    """Memorized collection of recently opened files"""

    def __init__(self, open_file_slot, settings_key, menu):
        super().__init__()
        self.list = list()
        self.open_file_slot = open_file_slot
        self.settings_key = settings_key
        self.menu = menu
        settings = QtCore.QSettings()
        file_list = settings.value(settings_key)
        if file_list is not None:
            for file_name in file_list:
                recent_file = RecentFile(file_name, self.open_file_slot)
                self.list.append(recent_file)
                recent_file.file_not_found.connect(self.on_file_not_found)
        self.update()

    def add_file(self, file_name):
        item = RecentFile(file_name, self.open_file_slot)
        if (len(self.list) > 0) and (self.list[0] == item):
            return  # No action; it's already there
        if item in self.list:
            self.list.remove(item)  # it might be later in the list
        item.file_not_found.connect(self.on_file_not_found)
        self.list.insert(0, item)  # make it the first in this list
        if len(self.list) > 10:
            self.list[:] = self.list[:10]
        # List changed, so save it to the registry
        settings = QtCore.QSettings()
        file_list = [x.file_name for x in self.list]
        settings.setValue(self.settings_key, file_list)
        self.update()

    @QtCore.Slot(str)
    def on_file_not_found(self, file_path):
        print("on_file_not_found")
        self.list.remove(file_path)
        settings = QtCore.QSettings()
        file_list = [x.file_name for x in self.list]
        settings.setValue(self.settings_key, file_list)
        self.update()
        QtWidgets.QMessageBox.warning(
            self.menu,
            f"File not found",
            f"File not found '{file_path}'",
            QtWidgets.QMessageBox.Ok,
            QtWidgets.QMessageBox.Ok,
        )

    def update(self):
        if len(self.list) > 0:
            self.menu.clear()
            for a in self.list:
                self.menu.addAction(a)
            self.menu.menuAction().setVisible(True)
        else:
            self.menu.menuAction().setVisible(False)
