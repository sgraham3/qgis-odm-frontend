# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject
from .odm_dialog import ODMDialog
from . import resources_rc

class ODMPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        
    def initGui(self):
        # Use custom drone icon
        self.action = QAction(QIcon(":/plugins/odm_frontend/drone.svg"), 'ODM Frontend', self.iface.mainWindow())
        
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu('ODM Frontend', self.action)
        self.iface.addToolBarIcon(self.action)
        
    def unload(self):
        self.iface.removePluginMenu('ODM Frontend', self.action)
        self.iface.removeToolBarIcon(self.action)
        
    def run(self):
        dialog = ODMDialog(self.iface)
        dialog.exec_()