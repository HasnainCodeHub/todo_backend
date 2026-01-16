"""Standardized error response utilities for MCP tools."""

from typing import Any, Dict, Optional
from datetime import datetime
import traceback


def create_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    tool_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response following the format:
    {
        "success": False,
        "data": None,
        "error": {
            "code": "...",
            "message": "...",
            "details": {...}
        },
        "metadata": {
            "tool": "...",
            "timestamp": "...",
            "user_id": "..."
        }
    }
    """
    return {
        "success": False,
        "data": None,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {}
        },
        "metadata": {
            "tool": tool_name or "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id or "unknown"
        }
    }


def create_success_response(
    data: Any,
    message: Optional[str] = None,
    user_id: Optional[str] = None,
    tool_name: str = "unknown"
) -> Dict[str, Any]:
    """
    Create a standardized success response following the format:
    {
        "success": True,
        "data": ...,
        "error": None,
        "metadata": {
            "tool": "...",
            "timestamp": "...",
            "user_id": "..."
        }
    }
    """
    response = {
        "success": True,
        "data": data,
        "error": None,
        "metadata": {
            "tool": tool_name,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id or "unknown"
        }
    }

    if message:
        response["message"] = message

    return response


def handle_mcp_tool_error(
    exception: Exception,
    tool_name: str,
    user_id: Optional[str] = None,
    additional_details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle exceptions in MCP tools and return standardized error responses.

    Args:
        exception: The caught exception
        tool_name: Name of the tool that failed
        user_id: User ID associated with the request
        additional_details: Additional context-specific details

    Returns:
        Standardized error response
    """
    # Map specific exception types to error codes
    if isinstance(exception, ValueError):
        error_code = "VALIDATION_ERROR"
        message = str(exception)
    elif isinstance(exception, PermissionError):
        error_code = "FORBIDDEN"
        message = "Access denied: insufficient permissions"
    elif isinstance(exception, FileNotFoundError):
        error_code = "NOT_FOUND"
        message = "Requested resource not found"
    else:
        error_code = "INTERNAL_ERROR"
        message = f"An internal error occurred: {str(exception)}"

        # For internal errors, log the full traceback for debugging
        print(f"Internal error in {tool_name}: {traceback.format_exc()}")

    details = {
        "exception_type": type(exception).__name__,
        "raw_message": str(exception)
    }

    if additional_details:
        details.update(additional_details)

    return create_error_response(
        error_code=error_code,
        message=message,
        details=details,
        user_id=user_id,
        tool_name=tool_name
    )


def validate_required_fields(data: Dict[str, Any], required_fields: list) -> Dict[str, Any]:
    """
    Validate that required fields are present in the input data.

    Args:
        data: Input data dictionary
        required_fields: List of required field names

    Returns:
        Dictionary with validation results
    """
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            missing_fields.append(field)

    if missing_fields:
        return {
            "valid": False,
            "missing_fields": missing_fields,
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }

    return {"valid": True}


def validate_string_field(value: str, field_name: str, min_length: int = 1, max_length: int = 200) -> Dict[str, Any]:
    """
    Validate a string field with length constraints.

    Args:
        value: String value to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length

    Returns:
        Dictionary with validation results
    """
    if not isinstance(value, str):
        return {
            "valid": False,
            "message": f"{field_name} must be a string"
        }

    if len(value) < min_length:
        return {
            "valid": False,
            "message": f"{field_name} must be at least {min_length} character(s)"
        }

    if len(value) > max_length:
        return {
            "valid": False,
            "message": f"{field_name} must be no more than {max_length} characters"
        }

    return {"valid": True}


def validate_task_data(title: str, description: str = None) -> Dict[str, Any]:
    """
    Validate task creation/update data.

    Args:
        title: Task title
        description: Task description (optional)

    Returns:
        Dictionary with validation results
    """
    # Validate title
    title_validation = validate_string_field(title, "title", min_length=1, max_length=200)
    if not title_validation["valid"]:
        return title_validation

    # Validate description if provided
    if description is not None:
        desc_validation = validate_string_field(description, "description", min_length=0, max_length=1000)
        if not desc_validation["valid"]:
            return desc_validation

    return {"valid": True}


def validate_task_id(task_id: int) -> Dict[str, Any]:
    """
    Validate task ID.

    Args:
        task_id: Task ID to validate

    Returns:
        Dictionary with validation results
    """
    if task_id is None:
        return {
            "valid": False,
            "message": "Task ID is required"
        }

    if not isinstance(task_id, int) or task_id <= 0:
        return {
            "valid": False,
            "message": f"Task ID must be a positive integer, got: {task_id}"
        }

    return {"valid": True}


def validate_boolean_field(value: bool, field_name: str) -> Dict[str, Any]:
    """
    Validate a boolean field.

    Args:
        value: Boolean value to validate
        field_name: Name of the field for error messages

    Returns:
        Dictionary with validation results
    """
    if value is None:
        return {"valid": True}  # Allow None for optional fields

    if not isinstance(value, bool):
        return {
            "valid": False,
            "message": f"{field_name} must be a boolean value"
        }

    return {"valid": True}