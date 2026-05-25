"""Check Terraform main.tf module references resolve to real directories."""
import os
import re

tf_root = r'c:\Users\olami\OneDrive\Desktop\DevOps\Tek-Watch\infrastructure\terraform'
main_tf = os.path.join(tf_root, 'main.tf')

issues = []

with open(main_tf, encoding='utf-8') as f:
    content = f.read()

# Find all source = "./modules/..." references
source_re = re.compile(r'source\s*=\s*"(\.\/[^"]+)"')
for match in source_re.finditer(content):
    src = match.group(1)
    resolved = os.path.normpath(os.path.join(tf_root, src))
    if not os.path.isdir(resolved):
        issues.append(f'Module source not found: {src} -> {resolved}')
    else:
        main = os.path.join(resolved, 'main.tf')
        if not os.path.exists(main):
            issues.append(f'Module missing main.tf: {resolved}')

# Check all module main.tf files exist
modules_dir = os.path.join(tf_root, 'modules')
for mod in os.listdir(modules_dir):
    mod_path = os.path.join(modules_dir, mod)
    if os.path.isdir(mod_path):
        main = os.path.join(mod_path, 'main.tf')
        if not os.path.exists(main):
            issues.append(f'Module {mod} missing main.tf')

# Check outputs.tf and variables.tf exist
for fname in ('outputs.tf', 'variables.tf'):
    if not os.path.exists(os.path.join(tf_root, fname)):
        issues.append(f'Missing {fname}')

if issues:
    for i in issues:
        print('TF ISSUE:', i)
else:
    print('All Terraform module references valid')
    mods = [m for m in os.listdir(modules_dir) if os.path.isdir(os.path.join(modules_dir, m))]
    print(f'Modules found: {sorted(mods)}')
