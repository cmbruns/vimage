from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt


# CircularListView allows circular navigation when the ComboBox is expanded to show all items
class CircularListView(QtWidgets.QListView):
    """
    CircularListView allows circular navigation.
    So moving down from the bottom item selects the top item,
    and moving up from the top item selects the bottom item.
    """

    def moveCursor(
        self,
        cursor_action: QtWidgets.QAbstractItemView.CursorAction,
        modifiers: Qt.KeyboardModifier,
    ) -> QtCore.QModelIndex:
        selected = self.selectedIndexes()
        if len(selected) != 1:
            return super().moveCursor(cursor_action, modifiers)
        index: QtCore.QModelIndex = selected[0]  # noqa
        # Guard against an empty model
        model = self.model()
        if not model or model.rowCount() == 0:
            return super().moveCursor(cursor_action, modifiers)
        top = 0
        bottom = self.model().rowCount() - 1
        ca = QtWidgets.QAbstractItemView.CursorAction
        # When trying to move up from the top item, wrap to the bottom item
        if index.row() == top and cursor_action == ca.MoveUp:
            return self.model().index(bottom, index.column(), index.parent())
        # When trying to move down from the bottom item, wrap to the top item
        elif index.row() == bottom and cursor_action == ca.MoveDown:
            return self.model().index(top, index.column(), index.parent())
        else:
            return super().moveCursor(cursor_action, modifiers)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """Enables circular mouse wheel wrapping when the popup menu is open."""
        model = self.model()
        if not model or model.rowCount() <= 1:
            super().wheelEvent(event)
            return

        # Get currently highlighted item in the popup list
        current_index = self.currentIndex()
        if not current_index.isValid():
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y()
        row = current_index.row()

        if delta < 0:  # Scroll down
            new_row = (row + 1) % model.rowCount()
        elif delta > 0:  # Scroll up
            new_row = (row - 1) % model.rowCount()
        else:
            return

        new_index = model.index(new_row, current_index.column(), current_index.parent())
        self.setCurrentIndex(new_index)
        event.accept()


class CircularComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        view = CircularListView(self.view().parent())
        self.setView(view)

    def _activate_next(self) -> None:
        if self.count() <= 1:
            return
        index = (self.currentIndex() + 1) % self.count()
        self.setCurrentIndex(index)

    def _activate_previous(self):
        if self.count() <= 1:
            return
        index = (self.currentIndex() - 1) % self.count()
        self.setCurrentIndex(index)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # Ignore modifiers like Alt (so Alt + Down still opens the popup natively)
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Down:
            self._activate_next()
        elif event.key() == Qt.Key.Key_Up:
            self._activate_previous()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        # Let the standard wheel logic handle it if the popup view is currently open
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta < 0:
            self._activate_next()
        elif delta > 0:
            self._activate_previous()
        event.accept()
