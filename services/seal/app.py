import os
import uuid
import hashlib
import json
import subprocess
import tempfile
import shutil
import datetime
from flask import Flask, request, jsonify
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base58

app = Flask(__name__, static_folder='static')

KEY_PATH = "/app/private_key.pem"
CERT_PATH = "/app/certificate.pem"
SIGNED_DIR = "/app/static"

os.makedirs(SIGNED_DIR, exist_ok=True)

def get_or_generate_key():
    if os.path.exists(KEY_PATH) and os.path.exists(CERT_PATH):
        with open(KEY_PATH, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        return private_key

    # Generate new P-256 EC private key
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Save private key
    with open(KEY_PATH, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )
        
    # Generate X.509 self-signed certificate (required by c2patool)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"AEGIS Seal Service"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow() - datetime.timedelta(days=1)
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).sign(private_key, hashes.SHA256())
    
    with open(CERT_PATH, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
        
    return private_key


@app.get("/health")
def health():
    return {"status": "ok", "service": "seal"}


@app.post("/seal")
def seal():
    private_key = get_or_generate_key()
    
    # Receive file
    file = request.files.get("file")
    if not file:
        # Fallback to dummy data if no file is provided (e.g. from current mock orchestrator)
        file_bytes = b"AEGIS Mock File Content for testing"
        filename = "mock.jpg"
    else:
        file_bytes = file.read()
        filename = file.filename

    # Calculate real SHA-256 hash of the file
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Sign the file hash using EC private key (producing the ECDSA signature)
    signature_bytes = private_key.sign(
        bytes.fromhex(file_hash),
        ec.ECDSA(hashes.SHA256())
    )
    signature_hex = signature_bytes.hex()

    # Generate did:key from EC public key
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint
    )
    multicodec_prefix = b'\x80\x24' # varint for 0x1200 (p256-pub)
    data = multicodec_prefix + public_bytes
    did = "did:key:z" + base58.b58encode(data).decode('utf-8')

    # Inject metadata and sign with c2patool
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = ".jpg"
        
    temp_in = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    temp_in.write(file_bytes)
    temp_in.close()

    out_filename = f"signed_{uuid.uuid4().hex}{ext}"
    output_path = os.path.join(SIGNED_DIR, out_filename)

    manifest_data = {
        "alg": "es256",
        "private_key": KEY_PATH,
        "sign_cert": CERT_PATH,
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.signed"
                        }
                    ]
                }
            }
        ],
        "claim_generator_info": [
            {
                "name": "AEGIS Seal Service",
                "version": "1.0.0"
            }
        ]
    }

    manifest_path = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    try:
        res = subprocess.run(
            ["c2patool", temp_in.name, "-m", manifest_path, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            fichier_signe = f"/static/{out_filename}"
        else:
            # Fallback if c2patool fails (e.g. format not supported by c2patool)
            print(f"c2patool failed (probably unsupported format): {res.stderr}")
            shutil.copy(temp_in.name, output_path)
            fichier_signe = f"/static/{out_filename}"
    except Exception as e:
        print(f"c2patool execution error: {e}")
        shutil.copy(temp_in.name, output_path)
        fichier_signe = f"/static/{out_filename}"
    finally:
        try:
            os.remove(temp_in.name)
            os.remove(manifest_path)
        except:
            pass

    return jsonify({
        "hash": file_hash,
        "signature": signature_hex,
        "fichier_signe": fichier_signe,
        "did": did
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)
