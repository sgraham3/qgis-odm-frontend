# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from .odm_dialog import ODMDialog
from . import resources_rc

class ODMPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dock = None
        self.photos_dock = None
        
    def initGui(self):
        # Use custom drone icon
        self.action = QAction(QIcon(":/plugins/odm_frontend/drone.svg"), 'ODM Frontend', self.iface.mainWindow())
        
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu('ODM Frontend', self.action)
        self.iface.addToolBarIcon(self.action)
        
    def unload(self):
        self.iface.removePluginMenu('ODM Frontend', self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock:
            self.iface.removeDockWidget(self.dock)
        if self.photos_dock:
            self.iface.removeDockWidget(self.photos_dock)
        
    def run(self):
        if self.dock is None:
            self.dock = ODMDialog(self.iface)
            self.dock.setObjectName('odm_main_dock')
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        else:
            # Toggle visibility
            if self.dock.isVisible():
                self.dock.hide()
                # Also hide photos dock if it exists
                if hasattr(self.dock, 'photos_dock') and self.dock.photos_dock:
                    self.dock.photos_dock.hide()
            else:
                self.dock.show()