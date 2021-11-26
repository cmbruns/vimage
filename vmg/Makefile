# Update UI class as needed using a custom Makefile and build rule,
# because PySide6/PyInstaller/pkg_resources/loadUiType combo is not working.
# This is not pythonic but you gotta do what you gotta do.
ui_vimage.py: vimage.ui
	pyside6-uic vimage.ui > ui_vimage.py
