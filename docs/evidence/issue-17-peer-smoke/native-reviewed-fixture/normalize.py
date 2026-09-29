def normalize_label(text: str) -> str:
    return " ".join(text.split()).casefold()
