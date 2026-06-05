from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


def validate_traceability(script: dict, traceability: dict) -> ValidationResult:
    mapped = {item["content_block_id"] for item in traceability.get("mappings", [])}
    missing: list[str] = []
    for scene in script.get("scenes", []):
        for block in scene.get("content_blocks", []):
            block_id = block.get("content_block_id")
            if block_id not in mapped:
                missing.append(block_id or "<missing>")
    return ValidationResult(valid=not missing, errors=missing)

