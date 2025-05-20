from gevent.monkey import patch_all

patch_all()

from howler.app import app
