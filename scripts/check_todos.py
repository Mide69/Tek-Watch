"""Find TODO/FIXME/placeholder items in source files."""
import os
import re

root = r'c:\Users\olami\OneDrive\Desktop\DevOps\Tek-Watch'
skip_dirs = {'__pycache__', '.git', 'node_modules', '.next', 'venv', 'scripts'}
skip_files = {'COMPLETION_SUMMARY.md', 'DEVELOPMENT.md', 'PROJECT_STATUS.md',
              'README.md', 'DEPLOYMENT.md', 'TESTING.md', 'FRONTEND_COMPLETION.md'}

todo_re = re.compile(r'(TODO|FIXME|HACK|XXX|NotImplemented|raise NotImplementedError|pass\s*#\s*TODO)', re.IGNORECASE)
placeholder_re = re.compile(r'(not yet implemented|placeholder|coming soon|stub)', re.IGNORECASE)

findings = []

for dirpath, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for fname in files:
        if fname in skip_files:
            continue
        if not fname.endswith(('.py', '.ts', '.tsx', '.tf')):
            continue
        fpath = os.path.join(dirpath, fname)
        rel = fpath.replace(root + os.sep, '')
        try:
            with open(fpath, encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    if todo_re.search(line) or placeholder_re.search(line):
                        findings.append(f'{rel}:{lineno}: {line.strip()[:100]}')
        except Exception:
            pass

if findings:
    print(f'Found {len(findings)} TODO/placeholder items:')
    for f in findings:
        print(' ', f)
else:
    print('No TODO/placeholder items found')
