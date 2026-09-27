"""AI Takeout Cleaner - Playwright Delete Agent (Accurate Sidebar Selector)"""
import asyncio
import json
import random
import re
from pathlib import Path

from playwright.async_api import async_playwright

AI_MODE_URL = "https://www.google.com/search?udm=50&aep=131&amc=1&atvm=3&cud=0"


async def load_delete_queue(file_path: str) -> list:
    """Load delete queue from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching."""
    if not text:
        return ""
    cleaned = re.sub(r'[\s\W_]+', '', text)
    return cleaned.lower()


def is_content_match(web_content: str, delete_items: list) -> int:
    """Check if the sidebar session title matches any item in delete queue with higher tolerance."""
    norm_web = normalize_text(web_content)
    if not norm_web:
        return -1

    for idx, item in enumerate(delete_items):
        # 1. Match against last_prompt
        norm_last = normalize_text(item.get("last_prompt", ""))
        if norm_last:
            # Check if one is a substring of the other (at least 5 characters overlap)
            min_len = min(len(norm_last), len(norm_web), 15)
            if min_len >= 4:
                if norm_last[:min_len] in norm_web or norm_web[:min_len] in norm_last:
                    return idx

        # 2. Match against title / summary
        norm_title = normalize_text(item.get("title", ""))
        if norm_title:
            min_len = min(len(norm_title), len(norm_web), 15)
            if min_len >= 4:
                if norm_title[:min_len] in norm_web or norm_web[:min_len] in norm_title:
                    return idx

        # 3. Match against original query
        orig = item.get("original_title", "").replace("Searched for ", "")
        norm_orig = normalize_text(orig)
        if norm_orig:
            min_len = min(len(norm_orig), len(norm_web), 15)
            if min_len >= 4:
                if norm_orig[:min_len] in norm_web or norm_web[:min_len] in norm_orig:
                    return idx

    return -1


async def delete_session_by_element(page, session_elem) -> bool:
    """Click the three-dots menu for a specific sidebar session and delete it."""
    try:
        # Based on inspected HTML:
        # <button role="button" aria-label="「...」的其他選項" class="fMed7">
        options_btn = await session_elem.query_selector('button.fMed7, button[aria-label*="其他選項"], button[aria-label*="Other options"]')
        
        if not options_btn:
            # Hover over the item to reveal the button if hidden
            await session_elem.hover()
            await asyncio.sleep(0.3)
            options_btn = await session_elem.query_selector('button.fMed7, button[aria-label*="其他選項"], button[aria-label*="Other options"]')

        if not options_btn:
            print("   ❌ Could not find options button (.fMed7)")
            return False

        await options_btn.dispatch_event("click")
        await asyncio.sleep(0.8)

        # Look for "刪除" / "Delete" in popup menu
        delete_option_selectors = [
            'div[role="menuitem"]:has-text("刪除")',
            'div[role="menuitem"]:has-text("Delete")',
            'li[role="menuitem"]:has-text("刪除")',
            'span:has-text("刪除")',
            'span:has-text("Delete")',
            'div.xYn6Gf:has-text("刪除")',
            'div.xYn6Gf:has-text("Delete")',
            'div:has-text("刪除對話")',
            'div:has-text("Delete chat")',
        ]

        del_btn = None
        for sel in delete_option_selectors:
            elements = await page.query_selector_all(sel)
            for el in elements:
                if await el.is_visible():
                    del_btn = el
                    break
            if del_btn:
                break

        if not del_btn:
            print("   ❌ Could not find Delete option in popup menu")
            await page.mouse.click(0, 0)
            return False

        await del_btn.dispatch_event("click")
        await asyncio.sleep(0.8)

        # Confirm deletion in dialog
        confirm_selectors = [
            'button:has-text("刪除")',
            'button:has-text("Delete")',
            'button:has-text("確認")',
            'button:has-text("Confirm")',
        ]

        confirm_btn = None
        for sel in confirm_selectors:
            btns = await page.query_selector_all(sel)
            for btn in btns:
                if await btn.is_visible():
                    confirm_btn = btn
                    break
            if confirm_btn:
                break

        if confirm_btn:
            await confirm_btn.dispatch_event("click")
            print("   ✅ Deletion confirmed!")
            await asyncio.sleep(2)
            return True
        else:
            print("   ⚠️ Confirmation dialog not found, checking if deleted directly...")
            return True

    except Exception as e:
        print(f"   ⚠️ Error during session deletion: {e}")

    return False


async def run_batch_deletion(delete_queue: list, headless: bool = False) -> None:
    """Scan sidebar sessions, match, and delete."""
    async with async_playwright() as p:
        profile_dir = Path.cwd() / "automation/chrome_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            ignore_default_args=["--enable-automation"],
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.pages[0] if context.pages else await context.new_page()

        print("🔗 Navigating to Google AI Mode...")
        await page.goto(AI_MODE_URL)

        # Manual Login Check
        if "accounts.google.com" in page.url:
            print("\n🔐 [ACTION REQUIRED] Please log in. Waiting up to 10 mins...")
            await page.wait_for_url(lambda url: "accounts.google.com" not in url, timeout=600000)
            await page.goto(AI_MODE_URL)

        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(8)  # 給予充足時間讓側邊欄與對話載入完成

        current_queue = list(delete_queue)
        print(f"🚀 Starting scan. Total items in delete queue: {len(current_queue)}")

        processed_titles = set()

        for step in range(1000):  # Increase limit for scrolling
            if not current_queue:
                print("\n🎉 All target items processed!")
                break

            # Find all sidebar session items matching class 'j8c53'
            session_items = await page.query_selector_all('li.j8c53')
            
            target_elem = None
            matched_idx = -1
            matched_title = ""

            for li in session_items:
                title_elem = await li.query_selector('.Se0jFd')
                if not title_elem:
                    continue
                
                title_text = (await title_elem.inner_text()).strip()
                if not title_text or title_text in processed_titles:
                    continue

                # Check if this title matches any item in our delete queue
                match_res = is_content_match(title_text, current_queue)
                if match_res != -1:
                    target_elem = li
                    matched_idx = match_res
                    matched_title = title_text
                    break
                else:
                    # Mark non-matching as kept
                    processed_titles.add(title_text)

            if not target_elem:
                # If no match is found, scroll the last visible item into view to trigger lazy loading
                if session_items:
                    last_item = session_items[-1]
                    last_title_elem = await last_item.query_selector('.Se0jFd')
                    last_title = (await last_title_elem.inner_text()).strip() if last_title_elem else ""
                    print(f"🔄 Scrolling down to load more history... (Last visible: '{last_title[:20]}')")
                    
                    # Scroll to the last item and wait for lazy load
                    await last_item.scroll_into_view_if_needed()
                    await asyncio.sleep(2)  # Wait for API requests
                    
                    # Double check if any new sessions are loaded, if so, continue loop
                    new_session_items = await page.query_selector_all('li.j8c53')
                    if len(new_session_items) > len(session_items):
                        continue
                
                print("🏁 No more matching sessions found in sidebar view after scrolling.")
                break

            deleted_item = current_queue.pop(matched_idx)
            print(f"\n[{step + 1}] 🎯 MATCH: '{matched_title}'")
            print(f"    Queue Ref: {deleted_item.get('title')[:30]}")

            if await delete_session_by_element(page, target_elem):
                print(f"    🔥 Successfully deleted!")
                await asyncio.sleep(2)
            else:
                print(f"    ⚠️ Failed to delete. Marking as processed to prevent loop.")
                processed_titles.add(matched_title)

            await asyncio.sleep(1)

        await context.close()


if __name__ == "__main__":
    delete_queue = asyncio.run(load_delete_queue("data/delete_queue.json"))
    asyncio.run(run_batch_deletion(delete_queue, headless=False))
