def split_message(text: str, limit: int = 1900):
    chunks = []
    current = ""

    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current += ("\n" if current else "") + line

    if current:
        chunks.append(current)

    return chunks

def paginate(items, per_page=15):
    return [
        items[i:i + per_page]
        for i in range(0, len(items), per_page)
    ]