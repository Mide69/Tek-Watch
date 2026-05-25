"""Check for broken local imports in each Python package."""
import ast
import os
import sys

root = r'c:\Users\olami\OneDrive\Desktop\DevOps\Tek-Watch'

# Map package dirs to their module roots
packages = {
    'agent':           os.path.join(root, 'agent'),
    'api':             os.path.join(root, 'api'),
    'ingest-consumer': os.path.join(root, 'ingest-consumer'),
}

issues = []

def get_local_modules(pkg_root):
    """Get all importable module names in a package root."""
    modules = set()
    for dirpath, dirs, files in os.walk(pkg_root):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fname in files:
            if fname.endswith('.py'):
                rel = os.path.relpath(os.path.join(dirpath, fname), pkg_root)
                mod = rel.replace(os.sep, '.').replace('.py', '')
                if mod.endswith('.__init__'):
                    mod = mod[:-9]
                modules.add(mod)
                # Also add top-level package names
                parts = mod.split('.')
                for i in range(1, len(parts)+1):
                    modules.add('.'.join(parts[:i]))
    return modules

def check_imports(pkg_name, pkg_root):
    local_mods = get_local_modules(pkg_root)
    # Known third-party / stdlib prefixes to skip
    skip_prefixes = (
        'boto3','botocore','fastapi','pydantic','uvicorn','anthropic',
        'httpx','jose','yaml','ulid','csv','io','json','logging','os',
        'sys','time','abc','dataclasses','datetime','typing','hashlib',
        'secrets','uuid','asyncio','concurrent','signal','functools',
        'contextlib','importlib','collections','itertools','pathlib',
        'zipfile','tempfile','shutil','re','math','random','string',
        'enum','copy','inspect','traceback','warnings','weakref',
        'threading','multiprocessing','subprocess','socket','http',
        'urllib','email','base64','struct','binascii','codecs',
        'archive','aws_amplify','next','react',
    )

    for dirpath, dirs, files in os.walk(pkg_root):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fname in files:
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(dirpath, fname)
            rel = fpath.replace(pkg_root + os.sep, '')
            try:
                with open(fpath, encoding='utf-8') as f:
                    tree = ast.parse(f.read())
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    else:
                        names = [node.module] if node.module else []

                    for name in names:
                        if not name:
                            continue
                        top = name.split('.')[0]
                        if top in skip_prefixes:
                            continue
                        # Check if it's a local module
                        if name not in local_mods and top not in local_mods:
                            # Could be stdlib - skip common ones
                            try:
                                __import__(top)
                            except ImportError:
                                issues.append(f'[{pkg_name}] {rel}: cannot import "{name}"')

for pkg_name, pkg_root in packages.items():
    check_imports(pkg_name, pkg_root)

if issues:
    for i in issues:
        print('IMPORT ISSUE:', i)
else:
    print('All import checks passed')
