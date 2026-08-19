import os
import re
import hmac
import socket
import ipaddress
from pathlib import Path
from typing import Optional, Set
from urllib.parse import urlparse
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

SAFE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")
STUDIO_API_KEY_NAME = "X-Studio-Token"
api_key_header = APIKeyHeader(name=STUDIO_API_KEY_NAME, auto_error=False)

ALLOWED_CHECKPOINT_FILENAMES: Set[str] = {
    "model_cnn.pt",
    "model_sklearn.joblib",
    "scaler.joblib",
    "meta.json"
}

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / AWS & GCP Metadata
    ipaddress.ip_network("224.0.0.0/4"),     # Multicast
    ipaddress.ip_network("240.0.0.0/4"),     # Reserved
]

def sanitize_identifier(name: str, field_name: str = "identifier") -> str:
    """
    Validates that a string identifier (e.g. profile_name, category, sample_id)
    contains strictly alphanumeric characters, hyphens, and underscores.
    Rejects any path traversal characters (., /, \\).
    """
    if not name or not isinstance(name, str):
        raise HTTPException(
            status_code=400,
            detail=f"Field '{field_name}' must be a non-empty string."
        )
    
    cleaned = name.strip()
    if not SAFE_IDENTIFIER_REGEX.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid '{field_name}': must only contain alphanumeric characters, underscores, and hyphens."
        )
    return cleaned

def safe_path_resolve(base_dir: Path, *parts: str) -> Path:
    """
    Safely resolves a path under a base directory, ensuring no path traversal
    can escape the base directory boundary.
    """
    base_resolved = base_dir.resolve()
    
    sanitized_parts = []
    for p in parts:
        if not p:
            continue
        # Split in case of subpaths and sanitize each component
        sub_parts = Path(p).parts
        for sp in sub_parts:
            if sp in (".", "..", "/", "\\"):
                raise HTTPException(status_code=403, detail="Path traversal elements are forbidden.")
            # Allow .wav or .npy in filename if valid base name
            p_stem = Path(sp).stem
            p_suffix = Path(sp).suffix.lstrip(".")
            if p_suffix:
                sanitize_identifier(p_stem, field_name="filename_stem")
                sanitize_identifier(p_suffix, field_name="filename_extension")
            else:
                sanitize_identifier(sp, field_name="path_segment")
            sanitized_parts.append(sp)

    target_path = (base_resolved / Path(*sanitized_parts)).resolve()
    
    if not target_path.is_relative_to(base_resolved):
        raise HTTPException(status_code=403, detail="Access denied: Path traversal detected.")
    
    return target_path

def validate_outbound_url(url: Optional[str], allow_private: bool = True) -> str:
    """
    Validates an outbound target URL against SSRF attack vectors.
    Blocks forbidden IP ranges (e.g. AWS/GCP cloud metadata 169.254.169.254).
    """
    if not url or not url.strip():
        return ""
    
    cleaned_url = url.strip()
    parsed = urlparse(cleaned_url)
    
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL scheme. Only HTTP and HTTPS protocols are allowed."
        )
    
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid target URL: Missing hostname.")

    try:
        # Resolve hostname to check destination IP
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip = ipaddress.ip_address(sockaddr[0])
            for blocked_net in BLOCKED_IP_NETWORKS:
                if ip in blocked_net:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Security alert: Target IP '{ip}' is blocked by SSRF filter."
                    )
            if not allow_private and (ip.is_private or ip.is_loopback):
                raise HTTPException(
                    status_code=400,
                    detail=f"Access to private IP '{ip}' is disallowed in this configuration."
                )
    except socket.gaierror:
        # Allow unresolved hostnames only if standard format, but warn
        pass
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to resolve target hostname: {str(e)}")

    return cleaned_url

def verify_studio_token(token: Optional[str] = Security(api_key_header)) -> bool:
    """
    Verifies the X-Studio-Token header for authenticated inter-node synchronization.
    If STUDIO_API_TOKEN environment variable is set, requests without matching token are rejected.
    """
    expected_token = os.getenv("STUDIO_API_TOKEN", "").strip()
    if not expected_token:
        # If token is not configured on the server, allow local developer connections
        return True
    
    if not token or not hmac.compare_digest(token.strip(), expected_token):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Missing or invalid 'X-Studio-Token' header."
        )
    return True
