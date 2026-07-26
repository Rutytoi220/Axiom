import os
import ast

dirs = ["axiom/perception", "axiom/plugins", "axiom/sdk"]
output_dir = "tests"

def generate_test_file(module_path, module_name):
    with open(module_path, "r") as f:
        tree = ast.parse(f.read())
    
    test_code = f"import pytest\nfrom unittest.mock import MagicMock, patch\nimport {module_name}\n\n"
    
    has_tests = False
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("_") and node.name != "__init__":
                continue
            has_tests = True
            test_code += f"def test_{node.name}_cov():\n"
            test_code += f"    pass # TODO: call {module_name}.{node.name}\n\n"
        elif isinstance(node, ast.ClassDef):
            has_tests = True
            test_code += f"def test_class_{node.name}_cov():\n"
            test_code += f"    pass # TODO: instantiate {module_name}.{node.name}\n\n"
    
    if has_tests:
        test_file_name = f"test_cov_{module_name.replace('.', '_')}.py"
        with open(os.path.join(output_dir, test_file_name), "w") as f:
            f.write(test_code)

for d in dirs:
    for root, _, files in os.walk(d):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                filepath = os.path.join(root, file)
                module = filepath.replace("/", ".")[:-3]
                generate_test_file(filepath, module)
