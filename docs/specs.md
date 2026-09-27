# AI Mode Takeout Cleaner - Technical Specifications

## Overview
A tool to review, filter, and automatically delete unwanted Google Takeout AI Mode search prompts from Google My Activity.

## Data Format

### Input
Single JSON file (~3MB typical) with structure:
```json
{
  "header": "AI Mode",
  "title": "Searched for [query]",
  "time": "2026-09-12T09:01:56.147Z",
  "products": ["AI Mode"],
  "safeHtmlItem": {
    "html": "\\u003cdiv\\u003eYour prompt:\\u003c/div\\u003e..."
  }
}
```

### Key Fields
- `title`: Search query (human-readable)
- `time`: ISO8601 timestamp
- `safeHtmlItem.html`: Escaped HTML with full conversation (user prompt + AI response)

## Parsing Requirements

### Unescape Unicode Sequences
Transform `\u003cp\u003eYour prompt:\u003c/strong\u003e` → `<p>Your prompt:</p>`

Python approach:
```python
import html

def decode_escape_sequence(escaped_string):
    """Converts \\uXXXX sequences to actual HTML characters"""
    import re
    def replace_unicode(match):
        return chr(int(match.group(1), 16))
    return re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, escaped_string)

def extract_prompt_content(html_content):
    """Extract readable prompt from decoded HTML"""
    decoded = decode_escape_sequence(html_content)
    # Get first ~800 chars (prompt is near beginning)
    return html.unescape(decoded[:800])
```

### Extracted Fields for UI Display
| Field | Source | Purpose |
|-------|--------|---------|
| `time` | `item.time` | Timestamp sorting/filtering |
| `title` | `item.title` | Search query display |
| `preview` | `safeHtmlItem.html[:800]` | Content preview for decision making |

## UI Requirements

### Display Per Item
- **Checkbox**: Mark to keep or delete
- **Timestamp**: Display ISO8601 timestamp (formatted)
- **Title**: Search query shown as link/button
- **Preview**: First ~200 characters of prompt text (stripped of HTML tags)
- **Status indicator**: Visual badge for selected/unselected

### Features
- Infinite scroll or pagination for large lists
- "Select All Visible" / "Deselect All" buttons
- Export/submit button to generate deletion list
- Search/filter by keyword in title/preview

### Tech Stack
- Vanilla HTML + CSS (no framework needed)
- Simple JavaScript for interactions
- Optional: LocalStorage to persist user selections

## Playwright Automation Requirements

### Target
Delete items marked as "keep = false" from Google My Activity website.

### Delete Flow Per Item
1. Navigate to Google AI Mode activity page (via direct URL or search query)
2. Locate item in feed
3. Click delete button (ellipsis menu → delete)
4. Confirm deletion if dialog appears
5. Wait 2-3 seconds before next item (rate limiting)

### Error Handling
- Retry up to 3x with increasing delays (1s, 2s, 4s)
- Log failed items for manual review
- Handle captcha with human intervention path

## Output Files

### `to_keep.json`
List of items user marked as keep:
```json
{
    "indices": [0, 5, 8, ...],
    "selectedItems": [...]
}
```

### `to_delete_ids.json`
List of Google My Activity URLs to delete:
```json
{
    "urls": [
        {"time": "...", "url": "https://myactivity.google.com/activity/..."},
        ...
    ]
}
```

## Constraints

1. **No streaming**: Parse entire JSON file in memory (3MB is small)
2. **No LLM summarization for filtering**: Show raw content, let user decide
3. **Playwright headful mode**: Required to preserve login/state cookies
4. **Manual URL generation**: No API access → search by timestamp/keywords

## Future Enhancement Spec

### Post-review Rule Deduction
After manual review completes:
- Send `to_keep.json` items to LLM
- Ask for pattern/rules derived from kept items
- Output example prompt (e.g., "keep queries containing 'code' or from 2026")
- Apply rules automatically to future takeouts
