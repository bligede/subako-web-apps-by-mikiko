"""Create local Compose secrets once; never print their values."""
from pathlib import Path
import secrets

root=Path(__file__).resolve().parents[1]
folder=root/'.local'/'secrets'
folder.mkdir(parents=True,exist_ok=True)
for name in ['db_owner_password','db_api_password','db_ingest_password','demo_password']:
    target=folder/name
    if not target.exists():
        target.write_text(secrets.token_urlsafe(28),encoding='utf-8')
        try:target.chmod(0o600)
        except OSError:pass
print('Compose secret files ready in .local/secrets (ignored by Git). Existing values preserved.')
print('Demo accounts: viewer/operator/pekaseh/admin @demo.subako.local; password in .local/secrets/demo_password.')
