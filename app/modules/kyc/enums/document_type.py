"""KYC document type enumeration."""

import enum


class DocumentType(str, enum.Enum):
    GOVERNMENT_ID_FRONT = "government_id_front"
    GOVERNMENT_ID_BACK = "government_id_back"
    PROOF_OF_ADDRESS = "proof_of_address"
    SELFIE = "selfie"
