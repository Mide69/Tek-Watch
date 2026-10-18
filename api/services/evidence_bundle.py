"""Portable evidence bundle; verification code is included, not a hosted dependency."""
import base64
import hashlib
import inspect
import io
import json
import zipfile

from services import evidence


VERIFIER = '''import argparse, base64, hashlib, json, pathlib, subprocess, sys
import evidence
p = argparse.ArgumentParser()
p.add_argument('--expected-head', help='Previously trusted chain head, obtained separately')
p.add_argument('--ca-file', help='Trusted timestamp authority CA bundle')
p.add_argument('--tsa-cert', help='Timestamp authority intermediate/signing certificates')
a = p.parse_args()
root = pathlib.Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text())
entries = json.loads((root / 'entries.json').read_text())
if hashlib.sha256((root / 'entries.json').read_bytes()).hexdigest() != manifest['entries_sha256']:
    sys.exit('Entries do not match manifest')
r = evidence.verify(entries, expected_head=manifest['head'])
if not r['intact'] or not r.get('complete'):
    sys.exit('Incomplete or invalid chain')
if a.expected_head and manifest['head']['hash'] != a.expected_head:
    sys.exit('Head differs from separately trusted head')
verified = 0
for entry in entries:
    if entry['kind'] != evidence.ANCHOR:
        continue
    body = entry['body']
    token = base64.b64decode(body['token_b64'], validate=True)
    if hashlib.sha256(token).hexdigest() != body['token_sha256']:
        sys.exit('Timestamp response checksum mismatch')
    if body['anchored_hash'] != entry['prev_hash']:
        sys.exit('Timestamp targets the wrong chain head')
    if a.ca_file and a.tsa_cert:
        path = root / 'anchors' / (str(entry['seq']) + '.tsr')
        if path.read_bytes() != token:
            sys.exit('Timestamp file differs from hashed record')
        result = subprocess.run(['openssl', 'ts', '-verify', '-digest', body['anchored_hash'],
                                 '-in', str(path), '-CAfile', a.ca_file, '-untrusted', a.tsa_cert])
        if result.returncode:
            sys.exit('Timestamp signature verification failed')
        verified += 1
print('Complete hash chain verified; entries:', len(entries))
print('Timestamp signatures verified:', verified)
print('Separately trusted head checked:', bool(a.expected_head))
print('Without a trusted head or verified timestamp this proves internal consistency only.')
'''


def build_bundle(entries, head):
    checked = evidence.verify(entries, expected_head=head)
    if not checked["intact"] or not checked.get("complete"):
        raise ValueError("Cannot export an incomplete or invalid evidence chain")
    raw = evidence.canonical(entries).encode()
    manifest = {"format": "tekwatch-evidence-1", "head": {"seq": head["seq"], "hash": head["hash"]},
                "entries_sha256": hashlib.sha256(raw).hexdigest(), "entries": len(entries),
                "scope": "Hash links and sequence; signatures must be verified against a trusted authority.",
                "summary": "Display-only; assessment bodies are authoritative and hashed."}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
        bundle.writestr("entries.json", raw)
        bundle.writestr("evidence.py", inspect.getsource(evidence))
        bundle.writestr("verify.py", VERIFIER)
        bundle.writestr("README.txt", "Use the verifier from a trusted TekWatch release; the included copy is for convenience.\n"
                        "Extract into a directory and run python verify.py.\n"
                        "For independent anchors add --ca-file TRUSTED_CA.pem --tsa-cert TSA.pem.\n"
                        "Supply --expected-head HASH for a chain head trusted separately.\n"
                        "The manifest is not itself an independent trust anchor. Integrity is not observation accuracy or legal compliance.\n")
        for entry in entries:
            if entry["kind"] == evidence.ANCHOR:
                bundle.writestr("anchors/" + str(entry["seq"]) + ".tsr",
                                base64.b64decode(entry["body"]["token_b64"], validate=True))
    return buffer.getvalue()
