# AI Mode Takeout Cleaner - Implementation Plan

## Phase 0: Setup and Dependencies (Day 1)

### Install Requirements
```bash
pip install playwright
playwright install chromium
```

Required Python libraries: `requests`, `asyncio` (built-in)

### Project Structure
```
ai-mode-cleaner/
├── src/
│   ├── __init__.py
│   ├── parser.py              # JSON unescape & extraction
│   └── ui_generator.py        # HTML interface generator
├── automation/
│   └── delete_agent.py         # Playwright deletion logic
├── utils/
│   ├── helpers.py               # Date formatting, URL search builder
│   └── export.py                # JSON output generators
├── data/
│   ├── raw_input.json           # Google Takeout input
│   ├── selected_items.json      # User kept items
│   └── delete_queue.json        # URLs to delete
├── main.py                      # Entry point
└── requirements.txt
```

---

## Phase 1: JSON Parsing Engine (Day 1-2)

### Task 1.1: Unicode Unescape Utility (`src/parser.py`)
**Goal:** Decode Google Takeout's escaped HTML format

**Implementation Steps:**
1. Create function `decode_safe_html(escaped_str)`:
    - Handle `\uXXXX` → actual char conversion
    - Use regex `\\u([0-9a-fA-F]{4})` for matching
2. Create function `extract_prompt_preview(html_content, length=800)`:
    - Slice first N chars
    - Strip HTML tags with `re.sub(r'<[^>]+>', '', text)`
    - Return clean text for UI preview

**Test Cases:**
```python
# Input: "\\u003cp\\u003eYour prompt:\\u003c/p\\u003e\\u003cbr\\u003eHello world"
decode_safe_html(input) → "<p>Your prompt:</p><br>Hello world"

extract_prompt_preview(decoded, 50) → "prompt:<br>Hello w..."
```

### Task 1.2: Main Parser Module (`src/parser.py`)
**Goal:** Parse full JSON file into structured list of items

**Implementation Steps:**
1. `load_takeout_json(file_path)`: Load entire JSON with `json.load()`
2. Parse each item dict:
    ```python
    {
        'index': idx,
         'title': raw_title,
         'time': iso_timestamp,
         'preview': extract_prompt_preview(safeHtmlItem.html),
         'full_html': safeHtmlItem.html
     }
    ```

**Test Data:** Create sample `data/raw_input.json` with 10-20 real AI Mode items from takeout export.

**Acceptance Criteria:** 
- Can load and parse 3MB file in <5 seconds
- Preview text is readable, no escape sequences remain
- Index preserves original order for selection tracking

---

## Phase 2: Interactive UI Generator (Day 2-3)

### Task 2.1: HTML Template Generator (`ui_generator.py`)
**Goal:** Create review.html with checkboxes for each item

**Implementation Steps:**
1. Create Jinja2/Python template rendering that produces:
    - Each row: checkbox + timestamp + title + preview (first 200 chars)
    - Sticky header showing "X items kept / Y total"
2. Add JavaScript features:
    - `toggleSelection(index)`: Toggle keep/don't keep with visual feedback
    - `selectAll()`, `deselectAll()`: Bulk actions
    - `exportSelection()`: Save to `selected_items.json`

**Sample UI Structure:**
```javascript
<div class="item-row" data-index="0">
    <input type="checkbox" id="keep_0">
    <span>[2026-09-12T09:01:56Z]</span> 
    "Searched for API Mode"
    <p class="preview">Your prompt: what is ai mode...</p>
</div>
```

**Task 2.2: Styling (`styles.css`)**
- Item rows with padding, borders
- Selected state: green background highlight
- Preview text truncated at 200 chars with ellipsis
- Sticky header showing counter

**Acceptance Criteria:** 
- Renders all items from parsed JSON file
- Checkboxes functional (can select/deselect individually)
- Bulk actions work across visible items
- Page loads in <3 seconds

---

## Phase 3: Takeout to Delete Queue Generator (Day 3)

### Task 3.1: Selection Export (`utils/export.py`)
**Goal:** Convert user's kept selections into two outputs

**Implementation Steps:**
1. `generate_keep_list(selected_indices)` → `selected_items.json`:
    ```json
     {
         "totalItems": 542,
         "keptCount": 37,
         "keptIndices": [0, 5, 8, 92, ...],
         "keepDetails": [...]
     }
    ```

2. `generate_delete_queue(takeout_items, keep_indices)` → `delete_queue.json`:
    - For each unselected index, extract:
        - Title (search query string)
        - Time (for URL search filtering)
        - Original full HTML (for reference)

**Acceptance Criteria:** 
- Keeps file tracks exactly what user checked
- Delete queue contains all unchecked items
- File sizes are minimal (<100KB typical)

---

## Phase 4: Playwright Delete Automation (Day 4-6)

### Task 4.1: Browser Automation Setup (`automation/delete_agent.py`)
**Goal:** Load Chrome profile and navigate to My Activity page

**Implementation Steps:**
1. Set up async Playwright with headful mode:
    ```python
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            user_data_dir="~/.config/google-chrome/Default"  # Your Chrome profile
        )
        page = await browser.new_page()
```

2. Login handling (manual first-time):
    - Open `https://myactivity.google.com/` 
    - User logs in once with their Google account
    - Session cookies persist for subsequent runs

**Test:** Run manually to verify login persists across restarts.

---

### Task 4.2: Single Item Deletion Flow (`automation/delete_agent.py`)

**Goal:** Navigate, locate, delete ONE item from My Activity feed

**Implementation Steps:**
1. Search navigation:
    ```python
    # Build search query from item title
    search_query = f"{item.time.split('T')[0]} ai mode"  # Date + context
    await page.goto(f"https://myactivity.google.com/activity?q={search_query}")
    ```

2. Locate delete button:
    - Find element with selector `.activity-menu-item` or similar (adjust based on actual DOM)
    - Click three-dots menu → select "Delete"
- Click if confirmation dialog exists

3. Wait 2-3 seconds between deletions (rate limiting):
    ```python
    await asyncio.sleep(3 + random.uniform(0, 1))
    ```

**Test Case:** Delete ONE item manually, verify it's gone from activity feed.

---

### Task 4.3: Batch Deletion Loop (`automation/delete_agent.py`)

**Goal:** Process entire `delete_queue.json` list

**Implementation Steps:**
1. Load delete queue file
2. For each item:
    - Navigate to My Activity search page
    - Wait for DOM to load (page timeout: 30s)
    - Attempt delete → Confirm if needed → Mark as success/fail
3. Retry failed deletions up to 3x with exponential backoff

**Retry Logic:**
```python
async def delete_with_retry(item, max_retries=3):
    for attempt in range(max_retries):
        try:
            success = await perform_delete(item)
            if success:
                log_success(item['index'])
                break
        except Exception as e:
            wait_time = (2 ** attempt) * random.uniform(1, 3)
            await asyncio.sleep(wait_time)
    
    return False if not success else True
```

**Error Handling:**
- Log failed items to `failed_deletes.log` for manual review
- Handle captchas: Print message "CAPTCHA detected — log into browser and solve manually"

**Acceptance Criteria:** 
- Processes all 50+ items in queue without crash
- Rate limiting prevents Google blocking (~3s per item = ~2.5 minutes for 50 items)
- Failed deletions logged for retry

---

## Phase 5: Integration & Testing (Day 6-7)

### Task 5.1: Main Entry Point (`main.py`)
**Goal:** Orchestrate full pipeline

**Execution Steps:**
```python
async def main():
    # Step 1: Parse takeout JSON
    items = load_takeout_json("data/raw_input.json")
    
    # Step 2: Generate UI
    html_content = generate_review_ui(items)
    with open("review.html", "w") as f:
        f.write(html_content)
    print("✅ Review page generated: review.html")
    
    # Step 3: Wait for user to complete manual selection
    input("After selecting items, press Enter to continue...")
    
    # Step 4: Export deletion queue
    selected_indices = get_user_selections()  # Parse from selected_items.json
    delete_queue = generate_delete_queue(items, selected_indices)
    save_json("data/delete_queue.json", delete_queue)
    
    # Step 5: Run Playwright automation
    await run_batch_deletion(delete_queue)
    
    print("🎉 Cleanup complete!")
```

### Task 5.2: End-to-End Test
**Test Data:** 
- Create `data/raw_input.json` with 20 sample AI Mode items
- Manually edit `review.html` to keep ~5 items, delete others
- Run Playwright automation

**Validation Checkpoints:**
| Stage | Expected Result |
|-------|-----------------|
| After UI generation | `review.html` renders 20 checklist items |
| After selection export | `selected_items.json` has 5 items, rest in `delete_queue.json` |
| After deletion loop | 15 items removed from Google My Activity feed |
| Error handling | Failed deletions logged if captcha blocked |

---

## Phase 6: Future Enhancement - Rule Deduction (Day 7+)

### Task 6.1: LLM Integration for Rules (Optional)
**Goal:** Analyze kept items → derive deletion rules for future takeouts

**Implementation Steps:**
1. Send `selected_items.json` to local LLM (Ollama Qwen3:35b):
    ```python
    prompt = """Analyze these AI Mode search prompts and identify patterns.
    Input: {kept_prompts}
    Question: What characteristics suggest I should keep vs delete?"""
    
    response = ollama.chat("qwen3...", messages=[{"role": "user", "content": prompt}])
    rules = response.response  # e.g., "Keep queries containing 'API' or from 2026"
    ```

2. Output rules file `deletion_rules.json`:
    ```json
     {
         "rules": ["contains('API')", "after_date('2026-01-01')"],
         "confidence": 0.85,
         "examples": [...]
     }
    ```

3. Future takeout processing:
    - Auto-apply rules to pre-filter items before manual UI generation
    - User can override with manual selection

---

## Risk Mitigation

### Playwright Risks
1. **Google Captchas:** Add manual intervention step with `print("CAPTCHA detected, solve in browser window")`
2. **DOM selector changes:** Store current selectors in config file for easy updating
3. **Cookie expiry:** Check login status on startup; re-login if needed

### Performance Risks
1. **Delete latency:** If >300 items queue, suggest manual batch deletes (Playwright will be slow)
2. **Memory usage:** Parsing 3MB JSON is minimal—no streaming needed

---

## Estimated Timeline

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 0 | 1 hour | Dependencies installed |
| Phase 1 | 4 hours | Parser works on real takeout file |
| Phase 2 | 6 hours | Review UI rendered and functional |
| Phase 3 | 2 hours | Deletion queue exported correctly |
| Phase 4 | 8 hours | Playwright batch deletion working (manual testing required) |
| Phase 5 | 3 hours | Full pipeline end-to-end test passes |
| Phase 6 | 5 hours (optional) | Rule deduction added |

**Total:** ~29 hours across 7 days

---

## Next Steps to Start

1. **Set up environment:** Create project folder, install Playwright
2. **Test parsing first:** Try unescaping a single `safeHtmlItem.html` field
3. **Build minimal UI skeleton:** One checkbox showing one item's text
4. **Verify manual deletion flow:** Click delete button in My Activity page

Ready to start? Begin with **Phase 1, Task 1.1** (Parser). Let me know if specs are clear or need adjustment!
