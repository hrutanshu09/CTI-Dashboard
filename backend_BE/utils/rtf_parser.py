from striprtf.striprtf import rtf_to_text

def extract_text_from_rtf(rtf_content: str) -> str:
    try:
        return rtf_to_text(rtf_content)
    except Exception as e:
        raise ValueError(f"RTF parsing failed: {str(e)}")
