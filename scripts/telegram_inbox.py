import re

def parse_inbox_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line:
        return None
    parts = line.rsplit(None, 1)
    if len(parts) != 2:
        return None
    product, seq = parts[0].strip(), parts[1].strip()
    if not product or not re.match(r'^[0-9oOxX]{1,10}$', seq):
        return None
    return product, seq.lower()
