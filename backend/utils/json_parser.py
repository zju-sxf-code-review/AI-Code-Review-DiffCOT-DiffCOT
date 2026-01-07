#!/usr/bin/env python3
"""Utilities for parsing JSON from text output."""

import json
import re
import logging

# Configure logging
logger = logging.getLogger(__name__)


def fix_json_issues(text: str) -> str:
    """
    Fix common JSON issues that LLMs produce.

    Args:
        text: JSON text that may have issues

    Returns:
        Fixed JSON text
    """
    # Fix line ranges like "line": 145-162 -> "line": "145-162"
    # Match patterns like "line": 123-456 (number-number without quotes)
    text = re.sub(r'"line"\s*:\s*(\d+)\s*-\s*(\d+)', r'"line": "\1-\2"', text)

    # Fix trailing commas before closing braces/brackets
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    return text


def extract_json_from_text(text):
    """
    Extract JSON object from text, looking in various formats and locations.

    Args:
        text: The text that may contain JSON

    Returns:
        dict: Parsed JSON object if found, None otherwise
    """
    # First, try to fix common issues
    text = fix_json_issues(text)

    try:
        # First, try to extract JSON from markdown code blocks (with or without language tag)
        json_matches = [
            re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL),
            re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
        ]

        for json_match in json_matches:
            if json_match:
                try:
                    json_text = fix_json_issues(json_match.group(1))
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    continue

        # If no JSON found in code blocks, try to find JSON objects anywhere in the text
        # Find all potential JSON objects (looking for balanced braces)
        brace_count = 0
        json_start = -1
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    json_start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and json_start != -1:
                    # Found a complete JSON object
                    potential_json = text[json_start:i+1]
                    try:
                        fixed_json = fix_json_issues(potential_json)
                        return json.loads(fixed_json)
                    except json.JSONDecodeError:
                        # This wasn't valid JSON, continue looking
                        continue
    except Exception:
        pass

    return None


def parse_json_with_fallbacks(text, error_context=""):
    """
    Parse JSON from text with multiple fallback strategies and error handling.

    Args:
        text: The text to parse
        error_context: Context string for error messages

    Returns:
        tuple: (success, result) where result is either the parsed JSON dict or error info
    """
    # First, try to fix common issues
    fixed_text = fix_json_issues(text)

    try:
        # First, try direct JSON parsing
        return True, json.loads(fixed_text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from text
    extracted_json = extract_json_from_text(text)
    if extracted_json:
        return True, extracted_json

    # If all parsing failed, return error info
    error_msg = "Failed to parse JSON"
    if error_context:
        error_msg = f"{error_context}: {error_msg}"

    logger.error(f"{error_msg}. Raw output: {repr(text)}")
    return False, {"error": f"Invalid JSON response -- raw output: {repr(text)}"}