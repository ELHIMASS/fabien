import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["NEXA_DATA_DIR"] = _tmp
os.environ["NEXA_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
