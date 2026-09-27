"""AI Takeout Cleaner - Parser Module"""
import json
import re


def decode_safe_html(escaped_string: str) -> str:
    """Convert \\uXXXX unicode escape sequences to actual HTML characters."""
    def replace_unicode(match):
        return chr(int(match.group(1), 16))
    
    return re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, escaped_string)


def extract_prompt_preview(html_content: str, length: int = 800) -> str:
    """Extract first N characters of prompt, strip HTML tags for readability."""
    decoded = decode_safe_html(html_content)
    # Get first portion and remove HTML tags
    preview = decoded[:length]
    text_only = re.sub(r'<[^>]+>', '', preview)
    return text_only


def parse_takeout_json(file_path: str) -> list:
    """Parse Google Takeout JSON file into structured items."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    items = []
    for idx, item in enumerate(data):
        parsed_item = {
            'index': idx,
            'title': item.get('title', ''),
            'time': item.get('time', ''),
            'preview': extract_prompt_preview(item.get('safeHtmlItem', {}).get('html', '')),
            'full_html': item.get('safeHtmlItem', {}).get('html', '')
        }
        items.append(parsed_item)
    
    return items


def save_parsed_items(items: list, output_path: str) -> None:
    """Save parsed items to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    # Test with sample data
    print("Test parsing...")