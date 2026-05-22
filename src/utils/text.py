"""Text formatting and normalization utilities."""

def normalize_paragraph_spacing(text: str) -> str:
    """Normalize paragraph spacing to ensure that paragraphs are separated by exactly one blank line.

    If paragraphs are separated by single newlines, they will be separated by double newlines.
    Multiple consecutive blank lines will be reduced to a single blank line.
    """
    if not text:
        return ""
    # Replace carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split the text by newline
    lines = text.split("\n")
    # Clean up whitespace and rebuild with double newlines for non-empty lines
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned_lines.append(stripped)
    return "\n\n".join(cleaned_lines)
