"""A bounded external policy applied to the agent's own parsed answer."""
import re

OPERATIONS = {
    "keep": "Keep the list in its present order.",
    "reverse": "Reverse the entire list.",
    "sort": "Sort the list in ascending lexicographic order, retaining every duplicate.",
}


def in_scope(request):
    text = request.lower()
    title = re.search(r"\btitles?\b", text)
    order = re.search(r"\b(ascending|alphabetical(?:ly)?|a to z|a-z)\b", text)
    conflict = re.search(r"\b(descending|reverse|distinct|unique|chronological)\b", text)
    return bool(title and order and not conflict)


def apply_operation(operation, request, parsed_answer):
    if operation not in OPERATIONS:
        raise ValueError(f"Unknown list operation: {operation}")
    if not in_scope(request) or not isinstance(parsed_answer, list):
        return parsed_answer
    if not all(isinstance(item, str) for item in parsed_answer):
        return parsed_answer
    if operation == "sort":
        return sorted(parsed_answer)
    if operation == "reverse":
        return parsed_answer[::-1]
    return parsed_answer
