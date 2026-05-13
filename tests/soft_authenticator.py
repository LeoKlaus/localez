"""
Software authenticator for WebAuthn integration tests.

Generates real EC P-256 key pairs and produces correctly structured
WebAuthn registration and authentication payloads (fmt=none attestation).
"""
import base64
import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDSA,
    SECP256R1,
    generate_private_key,
)
from cryptography.hazmat.primitives.hashes import SHA256


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _cose_public_key(private_key) -> bytes:
    pub = private_key.public_key().public_numbers()
    x = pub.x.to_bytes(32, "big")
    y = pub.y.to_bytes(32, "big")
    return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: x, -3: y})


def _auth_data(rp_id: str, cred_id: bytes, cose_pub_key: bytes, *, sign_count: int = 0, flags: int = 0b01000101) -> bytes:
    """Build authenticatorData bytes.

    Default flags: UP=1, UV=1, AT=1 (user present + verified + attested credential included).
    For authentication responses, pass flags=0b00000101 (UP+UV, no AT).
    """
    rp_id_hash = hashlib.sha256(rp_id.encode()).digest()
    aaguid = b"\x00" * 16
    cred_id_len = struct.pack(">H", len(cred_id))
    attested = aaguid + cred_id_len + cred_id + cose_pub_key
    return rp_id_hash + struct.pack("B", flags) + struct.pack(">I", sign_count) + attested


def _auth_data_no_attested(rp_id: str, *, sign_count: int = 1) -> bytes:
    """authenticatorData for authentication (no attested credential data)."""
    rp_id_hash = hashlib.sha256(rp_id.encode()).digest()
    flags = 0b00000101  # UP + UV
    return rp_id_hash + struct.pack("B", flags) + struct.pack(">I", sign_count)


class SoftAuthenticator:
    """Stateful software authenticator holding one credential."""

    def __init__(self, rp_id: str, origin: str):
        self.rp_id = rp_id
        self.origin = origin
        self._private_key = generate_private_key(SECP256R1())
        self.credential_id: bytes = os.urandom(32)
        self.sign_count: int = 0
        self._cose_pub_key = _cose_public_key(self._private_key)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def registration_response(self, challenge: bytes) -> dict:
        """Build the credential dict expected by POST /passkey/register/complete."""
        client_data = json.dumps({
            "type": "webauthn.create",
            "challenge": _b64url(challenge),
            "origin": self.origin,
        }).encode()

        auth_data = _auth_data(self.rp_id, self.credential_id, self._cose_pub_key)
        attestation_object = cbor2.dumps({
            "fmt": "none",
            "attStmt": {},
            "authData": auth_data,
        })

        cred_id_b64 = _b64url(self.credential_id)
        return {
            "id": cred_id_b64,
            "rawId": cred_id_b64,
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64url(client_data),
                "attestationObject": _b64url(attestation_object),
            },
        }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authentication_response(self, challenge: bytes) -> dict:
        """Build the credential dict expected by POST /passkey/authenticate/complete."""
        self.sign_count += 1

        client_data = json.dumps({
            "type": "webauthn.get",
            "challenge": _b64url(challenge),
            "origin": self.origin,
        }).encode()

        auth_data = _auth_data_no_attested(self.rp_id, sign_count=self.sign_count)
        client_data_hash = hashlib.sha256(client_data).digest()
        signed_data = auth_data + client_data_hash
        signature = self._private_key.sign(signed_data, ECDSA(SHA256()))

        cred_id_b64 = _b64url(self.credential_id)
        return {
            "id": cred_id_b64,
            "rawId": cred_id_b64,
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64url(client_data),
                "authenticatorData": _b64url(auth_data),
                "signature": _b64url(signature),
                "userHandle": None,
            },
        }
