"""Hash-based ID generation."""

import uuid


def generate_id(prefix: str, existing_ids: set[str]) -> str:
    """Generate a short hex ID with the given prefix.

    Tries 4, 5, then 6 character lengths to avoid collisions.
    """
    hex_str = uuid.uuid4().hex
    for length in (4, 5, 6):
        candidate = f"{prefix}-{hex_str[:length]}"
        if candidate not in existing_ids:
            return candidate
    raise RuntimeError(f"ID collision after 6 chars for prefix {prefix}")
