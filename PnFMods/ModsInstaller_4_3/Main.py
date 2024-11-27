from xml.dom import minidom
from ModsInstaller import logging, ModsInstaller, mods_api
import time

API_VERSION = 'API_v1.0'
MOD_NAME = 'ModsInstaller'
MOD_VERSION = '4.3'
__author__ = 'Roslich, Monstrofil'

f = time.time()
logging('   [INFO]: %s' % time.ctime())
logging('   [INFO]: ModsInstaller v%s' % MOD_VERSION)

mi = ModsInstaller(MOD_VERSION)
logging('   [INFO]: processed %s mods in %s sec' % (mi.all, round(time.time() - f, 1)))
logging('   [INFO]: successfully installed %s, updated %s, already installed %s, with errors %s'
        % (mi.installed, mi.update, mi.skip, mi.error))
del mi
if not mods_api:
    try:
        raw_input("Press Enter to exit")
    except:
        input("Press Enter to exit")
