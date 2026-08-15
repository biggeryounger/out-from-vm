"""Common verified restore path for screen capture and image decoding."""
from pathlib import Path

from sqr.bundle.builder import BUNDLE_SUFFIX
from sqr.bundle.extractor import extract_directory_bundle, is_directory_bundle
from sqr.receiver.verifier import VerificationResult, verify_restored_file


def restore_verified_payload(
    restored,
    manifest,
    output_path,
    expected_sha256=None,
    expected_md5=None,
    expected_bytes=None,
):
    """Verify payload, then write a file or safely publish a directory bundle."""
    bundle = manifest.filename.endswith(BUNDLE_SUFFIX) or is_directory_bundle(restored)
    result = verify_restored_file(
        restored,
        manifest,
        expected_sha256=expected_sha256,
        expected_md5=expected_md5,
        expected_bytes=expected_bytes,
        require_utf8=not bundle,
    )
    actual_path = Path(output_path)
    if not result.success:
        return result, actual_path
    try:
        if bundle:
            actual_path = extract_directory_bundle(restored, actual_path)
        else:
            actual_path.parent.mkdir(parents=True, exist_ok=True)
            actual_path.write_bytes(restored)
    except (OSError, ValueError) as exc:
        result = VerificationResult(
            success=False,
            byte_count_match=result.byte_count_match,
            sha256_match=result.sha256_match,
            md5_match=result.md5_match,
            utf8_valid=result.utf8_valid,
            actual_bytes=result.actual_bytes,
            actual_sha256=result.actual_sha256,
            actual_md5=result.actual_md5,
            message="restore failed: %s" % exc,
        )
    return result, actual_path
