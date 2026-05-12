import webauthn
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
from webauthn.registration.verify_registration_response import VerifiedRegistration
from webauthn.authentication.verify_authentication_response import VerifiedAuthentication

from app.config import settings


def get_registration_options(user_id: bytes, username: str, existing_credential_ids: list[bytes]):
    exclude = [PublicKeyCredentialDescriptor(id=cid) for cid in existing_credential_ids]
    return webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id,
        user_name=username,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        attestation=AttestationConveyancePreference.NONE,
    )


def verify_registration(credential: dict, expected_challenge: bytes) -> VerifiedRegistration:
    return webauthn.verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=settings.webauthn_rp_id,
        expected_origin=settings.webauthn_origin,
    )


def get_authentication_options(credential_ids: list[bytes] | None = None):
    allow = [PublicKeyCredentialDescriptor(id=cid) for cid in (credential_ids or [])]
    return webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )


def verify_authentication(
    credential: dict,
    expected_challenge: bytes,
    stored_public_key: bytes,
    stored_sign_count: int,
) -> VerifiedAuthentication:
    return webauthn.verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=settings.webauthn_rp_id,
        expected_origin=settings.webauthn_origin,
        credential_public_key=stored_public_key,
        credential_current_sign_count=stored_sign_count,
    )
