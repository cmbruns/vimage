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
        modifiers: Qt.KeyboardModifiers,
    ) -> QtCore.QModelIndex:
        selected = self.selectedIndexes()
        if len(selected) != 1:
            return super().moveCursor(cursor_action, modifiers)
        index: QtCore.QModelIndex = selected[0]  # noqa
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


class CircularComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        view = CircularListView(self.view().parent())
        self.setView(view)

    def _activate_next(self) -> None:
        index = (self.currentIndex() + 1) % self.count()
        self.setCurrentIndex(index)

    def _activate_previous(self):
        index = (self.currentIndex() - 1) % self.count()
        self.setCurrentIndex(index)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key_Down:
            self._activate_next()
        elif event.key() == Qt.Key_Up:
            self._activate_previous()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta < 0:
            self._activate_next()
        elif delta > 0:
            self._activate_previous()
