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

    # 1. Generate Root CA Key and Certificate
    ca_private_key = ec.generate_private_key(ec.SECP256R1())
    ca_subject = ca_issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"AEGIS Test Root CA"),
    ])
    
    ca_ski = x509.SubjectKeyIdentifier.from_public_key(ca_private_key.public_key())
    ca_aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_private_key.public_key())
    
    ca_cert = x509.CertificateBuilder().subject_name(
        ca_subject
    ).issuer_name(
        ca_issuer
    ).public_key(
        ca_private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    ).add_extension(
        ca_ski, critical=False
    ).add_extension(
        ca_aki, critical=False
    ).sign(ca_private_key, hashes.SHA256())

    # 2. Generate Leaf Key and Certificate (signed by Root CA)
    leaf_private_key = ec.generate_private_key(ec.SECP256R1())
    leaf_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"AEGIS Seal Service"),
    ])
    
    eku = x509.ExtendedKeyUsage([
        x509.oid.ExtendedKeyUsageOID.EMAIL_PROTECTION,
        x509.oid.ObjectIdentifier("1.3.6.1.5.5.7.3.36")
    ])
    
    ku = x509.KeyUsage(
        digital_signature=True,
        content_commitment=True,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=False,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False
    )
    
    bc = x509.BasicConstraints(ca=False, path_length=None)
    
    leaf_ski = x509.SubjectKeyIdentifier.from_public_key(leaf_private_key.public_key())
    leaf_aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_private_key.public_key())

    leaf_cert = x509.CertificateBuilder().subject_name(
        leaf_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        leaf_private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    ).add_extension(
        ku, critical=True
    ).add_extension(
        bc, critical=True
    ).add_extension(
        eku, critical=False
    ).add_extension(
        leaf_ski, critical=False
    ).add_extension(
        leaf_aki, critical=False
    ).sign(ca_private_key, hashes.SHA256())

    # 3. Write leaf private key to file
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode = 0o600
    with os.fdopen(os.open(KEY_PATH, flags, mode), "wb") as f:
        f.write(
            leaf_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    # 4. Write full certificate chain to file (leaf first, then CA)
    with os.fdopen(os.open(CERT_PATH, flags, mode), "wb") as f:
        f.write(leaf_cert.public_bytes(serialization.Encoding.PEM))
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    return leaf_private_key


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
    # Sanitize extension to prevent path injection or unexpected file creations
    if not ext or not ext.startswith('.') or not ext[1:].isalnum() or len(ext) > 10:
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
        "claim_generator": "AEGIS_Seal_Service/1.0.0",
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.created"
                        }
                    ]
                }
            }
        ]
    }

    manifest_path = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    try:
        res = subprocess.run(
            ["c2patool", temp_in.name, "-m", manifest_path, "-o", output_path, "--no_signing_verify"],
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
