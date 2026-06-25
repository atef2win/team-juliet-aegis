import os
import uuid
import hashlib
import json
import subprocess
import tempfile
import shutil
import datetime
import threading
import time
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

# Background thread to clean up signed files older than 1 hour (3600 seconds)
def cleanup_loop():
    while True:
        try:
            now = time.time()
            for filename in os.listdir(SIGNED_DIR):
                filepath = os.path.join(SIGNED_DIR, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    if now - stat.st_mtime > 3600:
                        os.remove(filepath)
                        print(f"Cleaned up expired file: {filename}")
        except Exception as e:
            print(f"Error in cleanup thread: {e}")
        time.sleep(300) # Run every 5 minutes

cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
cleanup_thread.start()

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


@app.get("/openapi.json")
def openapi():
    return jsonify({
        "openapi": "3.0.3",
        "info": {
            "title": "AEGIS Seal Service",
            "version": "1.0.0",
            "description": "Service de scellement cryptographique C2PA et signature de provenance pour le projet AEGIS."
        },
        "paths": {
            "/health": {
                "get": {
                    "summary": "Vérification de l'état de santé du service",
                    "responses": {
                        "200": {
                            "description": "Service opérationnel",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "example": "ok"},
                                            "service": {"type": "string", "example": "seal"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/seal": {
                "post": {
                    "summary": "Scelle un document avec signature C2PA et empreinte cryptographique",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "file": {
                                            "type": "string",
                                            "format": "binary",
                                            "description": "Le fichier de document à sceller"
                                        },
                                        "meta": {
                                            "type": "string",
                                            "description": "Métadonnées optionnelles au format JSON"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Fichier scellé avec succès",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "hash": {
                                                "type": "string",
                                                "description": "Empreinte SHA-256 du fichier original",
                                                "example": "dfd8f0d6c38836e3e73ef7f63e6d56d2f4f7e1c2ccc14b391819e165cec9c882"
                                            },
                                            "signature": {
                                                "type": "string",
                                                "description": "Signature ECDSA P-256 du hash, encodée en hexadécimal",
                                                "example": "30440220..."
                                            },
                                            "fichier_signe": {
                                                "type": "string",
                                                "description": "URL relative d'accès au fichier signé C2PA",
                                                "example": "/static/signed_abc123.jpg"
                                            },
                                            "did": {
                                                "type": "string",
                                                "description": "Decentralized Identifier did:key de la clé publique de scellement",
                                                "example": "did:key:zDnaewy..."
                                            },
                                            "c2pa_status": {
                                                "type": "string",
                                                "description": "Statut de l'injection C2PA",
                                                "example": "injected"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    })


@app.get("/docs")
def docs():
    swagger_html = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>AEGIS Seal Service - API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle-js"></script>
  <script>
    window.onload = () => {
      window.ui = SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger-ui',
      });
    };
  </script>
</body>
</html>"""
    return swagger_html


@app.post("/seal")
def seal():
    private_key = get_or_generate_key()
    
    # Receive file
    file = request.files.get("file")
    
    # Generate unique output filename
    if file and file.filename:
        filename = file.filename
    else:
        filename = "mock.jpg"
        
    ext = os.path.splitext(filename)[1].lower()
    # Sanitize extension to prevent path injection or unexpected file creations
    if not ext or not ext.startswith('.') or not ext[1:].isalnum() or len(ext) > 10:
        ext = ".jpg"
        
    temp_in = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    sha256 = hashlib.sha256()
    
    if not file:
        # Fallback to dummy data if no file is provided
        file_bytes = b"AEGIS Mock File Content for testing"
        sha256.update(file_bytes)
        temp_in.write(file_bytes)
        temp_in.close()
    else:
        # Optimized: Stream file directly from request stream to disk in chunks to minimize memory usage
        chunk_size = 65536 # 64KB
        while True:
            chunk = file.stream.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            temp_in.write(chunk)
        temp_in.close()

    # Calculate real SHA-256 hash of the file
    file_hash = sha256.hexdigest()

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

    c2pa_status = "injected"
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
            c2pa_status = f"skipped (c2patool error: {res.stderr.strip()})"
    except Exception as e:
        print(f"c2patool execution error: {e}")
        shutil.copy(temp_in.name, output_path)
        fichier_signe = f"/static/{out_filename}"
        c2pa_status = f"skipped (execution error: {str(e)})"
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
        "did": did,
        "c2pa_status": c2pa_status
    })


# Initialize key pair and cert chain on startup to avoid concurrent request race conditions
get_or_generate_key()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)
