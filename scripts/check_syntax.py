"""Check all Python files for syntax errors."""
import ast
import os

root = r'c:\Users\olami\OneDrive\Desktop\DevOps\Tek-Watch'
errors = []
checked = 0

for dirpath, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules', '.next', 'venv')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(dirpath, fname)
        rel = fpath.replace(root + os.sep, '')
        try:
            with open(fpath, encoding='utf-8') as f:
                src = f.read()
            ast.parse(src)
            checked += 1
        except SyntaxError as e:
            errors.append(f'{rel}: line {e.lineno}: {e.msg}')

if errors:
    for e in errors:
        print('SYNTAX ERROR:', e)
else:
    print(f'All {checked} Python files: no syntax errors')
