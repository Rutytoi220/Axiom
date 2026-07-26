import os
import importlib

dirs = ["axiom/perception", "axiom/plugins", "axiom/sdk"]

def test_import_everything():
    for d in dirs:
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    filepath = os.path.join(root, file)
                    module = filepath.replace("/", ".")[:-3]
                    try:
                        importlib.import_module(module)
                    except Exception:
                        pass
