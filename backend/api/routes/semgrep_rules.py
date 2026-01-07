"""API routes for managing Semgrep custom rules."""

import yaml
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/semgrep-rules", tags=["semgrep-rules"])

# Path to custom rules file
CUSTOM_RULES_PATH = Path(__file__).parent.parent.parent / "configs" / "semgrep_rules" / "custom_rules.yaml"


class SemgrepRule(BaseModel):
    """A single Semgrep rule."""
    id: str
    languages: List[str]
    severity: str
    message: str
    patterns: Optional[List[dict]] = None
    pattern: Optional[str] = None
    pattern_either: Optional[List[dict]] = None
    pattern_regex: Optional[str] = None
    metadata: Optional[dict] = None


class RuleListItem(BaseModel):
    """Simplified rule for list display."""
    id: str
    languages: List[str]
    severity: str


class RuleCreateRequest(BaseModel):
    """Request to create a new rule."""
    id: str
    languages: List[str]
    severity: str
    message: str
    pattern_type: str  # 'pattern', 'patterns', 'pattern-regex', 'pattern-either'
    pattern_content: str  # YAML string for the pattern section
    metadata: Optional[dict] = None


class RuleUpdateRequest(BaseModel):
    """Request to update an existing rule."""
    languages: Optional[List[str]] = None
    severity: Optional[str] = None
    message: Optional[str] = None
    pattern_type: Optional[str] = None
    pattern_content: Optional[str] = None
    metadata: Optional[dict] = None


def load_rules() -> dict:
    """Load rules from YAML file."""
    if not CUSTOM_RULES_PATH.exists():
        return {"rules": []}

    try:
        with open(CUSTOM_RULES_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if data else {"rules": []}
    except Exception as e:
        logger.error(f"Failed to load rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load rules: {str(e)}")


def save_rules(data: dict) -> None:
    """Save rules to YAML file."""
    try:
        # Ensure directory exists
        CUSTOM_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(CUSTOM_RULES_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
    except Exception as e:
        logger.error(f"Failed to save rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save rules: {str(e)}")


@router.get("/list", response_model=List[RuleListItem])
async def list_rules() -> List[RuleListItem]:
    """List all custom rules (id, languages, severity only)."""
    data = load_rules()
    rules = data.get("rules", [])

    result = []
    for rule in rules:
        if isinstance(rule, dict) and "id" in rule:
            result.append(RuleListItem(
                id=rule.get("id", ""),
                languages=rule.get("languages", []),
                severity=rule.get("severity", "INFO")
            ))

    # Sort by id
    result.sort(key=lambda r: r.id)
    return result


@router.get("/{rule_id}")
async def get_rule(rule_id: str) -> dict:
    """Get a single rule by ID."""
    data = load_rules()
    rules = data.get("rules", [])

    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            return rule

    raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")


@router.post("/create")
async def create_rule(request: RuleCreateRequest) -> dict:
    """Create a new rule."""
    data = load_rules()
    rules = data.get("rules", [])

    # Check if rule ID already exists
    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") == request.id:
            raise HTTPException(status_code=400, detail=f"Rule '{request.id}' already exists")

    # Build the new rule
    new_rule = {
        "id": request.id,
        "languages": request.languages,
        "severity": request.severity,
        "message": request.message,
    }

    # Parse pattern content from YAML string
    try:
        pattern_data = yaml.safe_load(request.pattern_content)
        if request.pattern_type == "pattern":
            new_rule["pattern"] = pattern_data if isinstance(pattern_data, str) else request.pattern_content
        elif request.pattern_type == "patterns":
            new_rule["patterns"] = pattern_data if isinstance(pattern_data, list) else [pattern_data]
        elif request.pattern_type == "pattern-regex":
            new_rule["pattern-regex"] = pattern_data if isinstance(pattern_data, str) else request.pattern_content
        elif request.pattern_type == "pattern-either":
            new_rule["pattern-either"] = pattern_data if isinstance(pattern_data, list) else [pattern_data]
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML in pattern_content: {str(e)}")

    # Add metadata if provided
    if request.metadata:
        new_rule["metadata"] = request.metadata

    # Add to rules list
    rules.append(new_rule)
    data["rules"] = rules

    save_rules(data)
    logger.info(f"Created new rule: {request.id}")

    return {"success": True, "rule": new_rule}


@router.put("/{rule_id}")
async def update_rule(rule_id: str, request: RuleUpdateRequest) -> dict:
    """Update an existing rule."""
    data = load_rules()
    rules = data.get("rules", [])

    # Find the rule
    rule_index = None
    for i, rule in enumerate(rules):
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            rule_index = i
            break

    if rule_index is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    # Update fields
    rule = rules[rule_index]

    if request.languages is not None:
        rule["languages"] = request.languages
    if request.severity is not None:
        rule["severity"] = request.severity
    if request.message is not None:
        rule["message"] = request.message
    if request.metadata is not None:
        rule["metadata"] = request.metadata

    # Update pattern if provided
    if request.pattern_type and request.pattern_content:
        # Remove old pattern fields
        for key in ["pattern", "patterns", "pattern-regex", "pattern-either"]:
            rule.pop(key, None)

        try:
            pattern_data = yaml.safe_load(request.pattern_content)
            if request.pattern_type == "pattern":
                rule["pattern"] = pattern_data if isinstance(pattern_data, str) else request.pattern_content
            elif request.pattern_type == "patterns":
                rule["patterns"] = pattern_data if isinstance(pattern_data, list) else [pattern_data]
            elif request.pattern_type == "pattern-regex":
                rule["pattern-regex"] = pattern_data if isinstance(pattern_data, str) else request.pattern_content
            elif request.pattern_type == "pattern-either":
                rule["pattern-either"] = pattern_data if isinstance(pattern_data, list) else [pattern_data]
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML in pattern_content: {str(e)}")

    rules[rule_index] = rule
    data["rules"] = rules

    save_rules(data)
    logger.info(f"Updated rule: {rule_id}")

    return {"success": True, "rule": rule}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str) -> dict:
    """Delete a rule by ID."""
    data = load_rules()
    rules = data.get("rules", [])

    # Find and remove the rule
    new_rules = [r for r in rules if not (isinstance(r, dict) and r.get("id") == rule_id)]

    if len(new_rules) == len(rules):
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    data["rules"] = new_rules
    save_rules(data)
    logger.info(f"Deleted rule: {rule_id}")

    return {"success": True, "message": f"Rule '{rule_id}' deleted"}


@router.get("/{rule_id}/yaml")
async def get_rule_yaml(rule_id: str) -> dict:
    """Get a single rule as YAML string for editing."""
    data = load_rules()
    rules = data.get("rules", [])

    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            # Convert rule to YAML string
            yaml_str = yaml.dump(rule, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
            return {"yaml": yaml_str, "rule": rule}

    raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")


@router.put("/{rule_id}/yaml")
async def update_rule_yaml(rule_id: str, yaml_content: dict) -> dict:
    """Update a rule from YAML string."""
    data = load_rules()
    rules = data.get("rules", [])

    # Parse the YAML content
    try:
        new_rule = yaml.safe_load(yaml_content.get("yaml", ""))
        if not isinstance(new_rule, dict):
            raise HTTPException(status_code=400, detail="Invalid YAML: must be a dictionary")
        if "id" not in new_rule:
            raise HTTPException(status_code=400, detail="Rule must have an 'id' field")
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")

    # Find and update the rule
    rule_index = None
    for i, rule in enumerate(rules):
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            rule_index = i
            break

    if rule_index is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    # If ID changed, check for conflicts
    if new_rule["id"] != rule_id:
        for rule in rules:
            if isinstance(rule, dict) and rule.get("id") == new_rule["id"]:
                raise HTTPException(status_code=400, detail=f"Rule '{new_rule['id']}' already exists")

    rules[rule_index] = new_rule
    data["rules"] = rules

    save_rules(data)
    logger.info(f"Updated rule from YAML: {rule_id} -> {new_rule['id']}")

    return {"success": True, "rule": new_rule}


@router.post("/validate")
async def validate_rule_yaml(yaml_content: dict) -> dict:
    """Validate a rule YAML without saving."""
    try:
        rule = yaml.safe_load(yaml_content.get("yaml", ""))
        if not isinstance(rule, dict):
            return {"valid": False, "error": "YAML must be a dictionary"}

        # Check required fields
        if "id" not in rule:
            return {"valid": False, "error": "Rule must have an 'id' field"}
        if "languages" not in rule:
            return {"valid": False, "error": "Rule must have a 'languages' field"}
        if "severity" not in rule:
            return {"valid": False, "error": "Rule must have a 'severity' field"}
        if "message" not in rule:
            return {"valid": False, "error": "Rule must have a 'message' field"}

        # Check for at least one pattern field
        pattern_fields = ["pattern", "patterns", "pattern-regex", "pattern-either"]
        has_pattern = any(field in rule for field in pattern_fields)
        if not has_pattern:
            return {"valid": False, "error": "Rule must have at least one pattern field (pattern, patterns, pattern-regex, or pattern-either)"}

        return {"valid": True, "rule": rule}
    except yaml.YAMLError as e:
        return {"valid": False, "error": f"Invalid YAML syntax: {str(e)}"}
