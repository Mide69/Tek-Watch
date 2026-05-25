"""Check TypeScript files for @/ imports that reference non-existent files."""
import os
import re

root = r'c:\Users\olami\OneDrive\Desktop\DevOps\Tek-Watch'
apps = {
    'dashboard':    os.path.join(root, 'dashboard', 'src'),
    'admin-portal': os.path.join(root, 'admin-portal', 'src'),
}

issues = []

def resolve_alias(imp: str, app_src: str) -> str:
    """Resolve @/ alias to absolute path."""
    rel = imp.replace('@/', '')
    return os.path.join(app_src, rel)

def file_exists_with_extensions(base: str) -> bool:
    """Check if file exists with any TS/TSX extension."""
    for ext in ('', '.ts', '.tsx', '/index.ts', '/index.tsx'):
        if os.path.exists(base + ext):
            return True
    return False

import_re = re.compile(r'''from\s+['"](@/[^'"]+)['"]''')

for app_name, src_root in apps.items():
    if not os.path.exists(src_root):
        issues.append(f'[{app_name}] src directory missing: {src_root}')
        continue

    for dirpath, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d != 'node_modules']
        for fname in files:
            if not fname.endswith(('.ts', '.tsx')):
                continue
            fpath = os.path.join(dirpath, fname)
            rel = fpath.replace(src_root + os.sep, '')
            with open(fpath, encoding='utf-8') as f:
                content = f.read()
            for match in import_re.finditer(content):
                imp = match.group(1)
                resolved = resolve_alias(imp, src_root)
                if not file_exists_with_extensions(resolved):
                    issues.append(f'[{app_name}] {rel}: missing import "{imp}" -> {resolved}')

if issues:
    for i in issues:
        print('MISSING:', i)
else:
    print('All TypeScript @/ imports resolve correctly')
