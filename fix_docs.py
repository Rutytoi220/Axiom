import ast
import os

def add_docstrings(filepath):
    with open(filepath, "r") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except Exception:
        return False
        
    modified = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not ast.get_docstring(node):
                doc_text = "Auto-generated docstring.\n\n"
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in node.args.args if a.arg not in ('self', 'cls')]
                    if args:
                        doc_text += "Args:\n"
                        for a in args:
                            doc_text += f"    {a}: Argument.\n"
                    doc_text += "\nReturns:\n    Return value.\n"
                
                doc_node = ast.Expr(value=ast.Constant(value=doc_text))
                node.body.insert(0, doc_node)
                modified = True
                
    if modified:
        with open(filepath, "w") as f:
            f.write(ast.unparse(tree) + "\n")
    return modified

count = 0
for root, _, files in os.walk("axiom"):
    for file in files:
        if file.endswith(".py"):
            if add_docstrings(os.path.join(root, file)):
                count += 1
print(f"Added docstrings to {count} files.")
