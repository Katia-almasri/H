"""Allowed file type enumeration for KYC uploads."""

import enum


class AllowedFileType(str, enum.Enum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    PDF = "application/pdf"
