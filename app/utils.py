import re

def render_text(text: str):
    """
    Detects if a string contains Arabic characters. 
    If yes, wraps it in an RTL div. If no, returns it normally for LTR.
    """
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', text))
    
    if has_arabic:
        rtl_html = f"""
        <div dir="rtl" style="text-align: right; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
            {text}
        </div>
        """
        return rtl_html
    
    return text