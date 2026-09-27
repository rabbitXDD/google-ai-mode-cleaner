"""AI Takeout Cleaner - JSON Parser"""
import json
import re
import html


def extract_title_from_summary(ai_response: str) -> str:
    """Extract a concise title from AI response summary."""
    if not ai_response:
        return ""
    # Try to find a heading-like phrase at the start
    # e.g., "「AI 模式」（AI Mode）是 Google 搜尋推出的一項對話式搜尋功能"
    # We want to extract the main subject
    text = ai_response.strip()

    # Remove markdown/HTML artifacts
    text = re.sub(r'\*\*|__|#|>|\[|\]|\(|\)', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.strip()

    # Take first sentence or first 30 chars as title
    sentences = re.split(r'[。！？\n]', text)
    if sentences:
        title = sentences[0].strip()
        if len(title) > 40:
            title = title[:40] + "..."
        return title
    return text[:40]


def parse_takeout_json(file_path: str) -> list:
    """Parse Google Takeout JSON file into structured items."""
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    parsed_items = []

    for entry in raw_data:
        # Only process entries with safeHtmlItem content
        if "safeHtmlItem" not in entry or not entry["safeHtmlItem"]:
            continue

        html_content = entry["safeHtmlItem"][0].get("html", "")

        # 1. Decode HTML entities and unicode escapes
        decoded_html = html.unescape(html_content)

        # 2. Extract ALL user prompts (same conversation may have multiple)
        prompt_matches = re.findall(
            r"Your prompt:</strong><br/?>\s*([\s\S]*?)(?=<p>|<strong>Search|\Z)",
            decoded_html, re.IGNORECASE
        )
        prompts = [re.sub(r'<[^>]+>', '', p).strip() for p in prompt_matches]

        # Use the LAST prompt as the last prompt (most recent in conversation)
        last_prompt = prompts[-1] if prompts else ""

        # 3. Extract AI response summary (use the last response block)
        response_matches = re.findall(
            r"Search(?:&#39;|')s response:</strong><br/?>\s*([\s\S]*?)(?=\Z)",
            decoded_html, re.IGNORECASE
        )
        ai_response = ""
        if response_matches:
            ai_response = re.sub(r'<[^>]+>', '', response_matches[-1]).strip()
            ai_response = ai_response[:200] + "..." if len(ai_response) > 200 else ai_response

        # 4. Generate title from AI summary
        summary_title = extract_title_from_summary(ai_response)

        clean_item = {
            "id": entry.get("time"),
            "title": summary_title if summary_title else (last_prompt[:40] if last_prompt else entry.get("title", "Untitled")),
            "last_prompt": last_prompt,
            "original_title": entry.get("title"),
            "time": entry.get("time"),
            "url": entry.get("titleUrl", ""),
            "summary": ai_response if ai_response else "No response summary",
            "image": entry.get("imageFile", "")
        }
        parsed_items.append(clean_item)

    return parsed_items


def save_parsed_items(items: list, output_path: str) -> None:
    """Save parsed items to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    print("Parser module loaded successfully")