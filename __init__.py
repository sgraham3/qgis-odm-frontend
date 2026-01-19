# -*- coding: utf-8 -*-
def classFactory(iface):
    from .odm_plugin import ODMPlugin
    return ODMPlugin(iface)