import unittest
import os
import hashlib
import json
import io
from app import app, KEY_PATH, CERT_PATH, SIGNED_DIR
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography import x509

class TestSealService(unittest.TestCase):
    def setUp(self):
        # Force certificate regeneration to use the new two-tier chain format
        if os.path.exists(KEY_PATH):
            try:
                os.remove(KEY_PATH)
            except:
                pass
        if os.path.exists(CERT_PATH):
            try:
                os.remove(CERT_PATH)
            except:
                pass
        # Configure Flask test client
        self.app = app.test_client()
        self.app.testing = True

    def test_health(self):
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "seal")

    def test_openapi_spec(self):
        response = self.app.get('/openapi.json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("openapi"), "3.0.3")
        self.assertIn("/seal", data.get("paths", {}))

    def test_swagger_ui(self):
        response = self.app.get('/docs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"swagger-ui", response.data)

    def test_seal_no_file(self):
        # Send empty POST request to /seal (simulate current mock orchestrator call)
        response = self.app.post('/seal')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn("hash", data)
        self.assertIn("signature", data)
        self.assertIn("fichier_signe", data)
        self.assertIn("did", data)
        
        # Verify hash match for mock content
        mock_content = b"AEGIS Mock File Content for testing"
        expected_hash = hashlib.sha256(mock_content).hexdigest()
        self.assertEqual(data["hash"], expected_hash)
        
        # Verify did format
        self.assertTrue(data["did"].startswith("did:key:z"))
        
        # Verify signature is cryptographically valid
        self.assertTrue(self.verify_signature(data["hash"], data["signature"]))

    def test_seal_with_file(self):
        # Simulate uploading a file
        file_content = b"Fake JPEG File Content"
        file_name = "test_image.jpg"
        
        response = self.app.post(
            '/seal',
            data={
                'file': (io.BytesIO(file_content), file_name)
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn("hash", data)
        self.assertIn("signature", data)
        self.assertIn("fichier_signe", data)
        self.assertIn("did", data)
        
        # Verify hash match
        expected_hash = hashlib.sha256(file_content).hexdigest()
        self.assertEqual(data["hash"], expected_hash)
        
        # Verify signature
        self.assertTrue(self.verify_signature(data["hash"], data["signature"]))
        
        # Verify that signed file was created and served
        static_filename = data["fichier_signe"].split("/static/")[-1]
        local_path = os.path.join(SIGNED_DIR, static_filename)
        self.assertTrue(os.path.exists(local_path))

    def test_seal_valid_png(self):
        # Generate a valid 100x100 PNG file using Pillow
        from PIL import Image
        img = Image.new('RGB', (100, 100), color = 'red')
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        png_content = img_byte_arr.getvalue()
        file_name = "test_image.png"
        
        response = self.app.post(
            '/seal',
            data={
                'file': (io.BytesIO(png_content), file_name)
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn("fichier_signe", data)
        
        static_filename = data["fichier_signe"].split("/static/")[-1]
        local_path = os.path.join(SIGNED_DIR, static_filename)
        self.assertTrue(os.path.exists(local_path))
        
        # Verify using c2patool that the manifest store was embedded successfully
        import subprocess
        res = subprocess.run(
            ["c2patool", local_path],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("AEGIS Seal Service", res.stdout)

    def verify_signature(self, file_hash, signature_hex):
        # Load the generated certificate
        self.assertTrue(os.path.exists(CERT_PATH))
        with open(CERT_PATH, "rb") as f:
            cert_data = f.read()
            
        cert = x509.load_pem_x509_certificate(cert_data)
        public_key = cert.public_key()
        
        # Verify the ECDSA signature of the hash
        try:
            public_key.verify(
                bytes.fromhex(signature_hex),
                bytes.fromhex(file_hash),
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception as e:
            print(f"Signature verification failed: {e}")
            return False

if __name__ == '__main__':
    unittest.main()
