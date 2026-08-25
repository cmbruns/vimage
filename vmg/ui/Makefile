# Update UI class as needed using a custom Makefile and build rule,
# because PySide6/PyInstaller/pkg_resources/loadUiType combo is not working.
# This is not pythonic but you gotta do what you gotta do.
all: ui_vimage.py ui_demosaic_dialog.py ui_log.py ui_lens_parameters.py

ui_vimage.py: vimage.ui
	pyside6-uic vimage.ui > ui_vimage.py

ui_demosaic_dialog.py: demosaic_dialog.ui
	pyside6-uic demosaic_dialog.ui > ui_demosaic_dialog.py

ui_lens_parameters.py: lens_parameters_dialog.ui
	pyside6-uic lens_parameters_dialog.ui > ui_lens_parameters.py

ui_log.py: log.ui
	pyside6-uic log.ui > ui_log.py