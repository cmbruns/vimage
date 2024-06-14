from PySide6.QtGui import QUndoCommand


class CropToSelection(QUndoCommand):
    def redo(self):
        print("redo")

    def undo(self):
        print("undo")
