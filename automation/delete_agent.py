"""AI Takeout Cleaner - Playwright Delete Agent (Accurate Sidebar Selector)"""
import asyncio
import json
import os
import re

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
    """Check if the sidebar session title matches any item in delete queue."""
    norm_web = normalize_text(web_content)
    if not norm_web:
        return -1

    for idx, item in enumerate(delete_items):
        # 1. Match against last_prompt
        norm_last = normalize_text(item.get("last_prompt", ""))
        if norm_last and norm_last in norm_web:
            return idx

        # 2. Match against title / summary
        norm_title = normalize_text(item.get("title", ""))
        if norm_title and norm_title in norm_web:
            return idx

        # 3. Match against original query
        orig = item.get("original_title", "").replace("Searched for ", "")
        norm_orig = normalize_text(orig)
        if norm_orig and norm_orig in norm_web:
            return idx

        # 4. Partial match - if web content contains key parts of search query
        if len(norm_web) >= 10:
            for key in [norm_last, norm_title, norm_orig]:
                if key and len(key) >= 10 and (key[:10] in norm_web):
                    return idx

    return -1


async def delete_session_by_element(page, session_elem) -> bool:
    """Click the three-dots menu for a specific sidebar session and delete it."""
    try:
        # Based on inspected HTML:
        # <button role="button" aria-label="「...」的其他選項" class="fMed7">
        options_btn = await session_elem.query_selector('button.fMed7, button[aria-label*="其他選項"], button[aria-label*="Other options"], button[role="button"]:has(svg)')
        
        if not options_btn:
            # Hover over the item to reveal the button if hidden
            await session_elem.hover()
            await asyncio.sleep(0.3)
            options_btn = await session_elem.query_selector('button.fMed7, button[aria-label*="其他選項"], button[aria-label*="Other options"], button[role="button"]:has(svg)')

        if not options_btn:
            # Fallback: try finding any button or clickable icon inside the item row
            options_btn = await session_elem.query_selector('button, [role="button"]')

        if not options_btn:
            print("   ❌ Could not find options button")
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


async def dump_page_structure(page, label="dump"):
    """Dump page HTML and interactive elements for debugging."""
    html = await page.content()
    dump_path = f"debug_{label}.html"
    with open(dump_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   📄 Page structure dumped to {dump_path}")

    # Also dump all li elements with their classes
    li_info = await page.evaluate("""() => {
        const lis = document.querySelectorAll('li');
        const results = [];
        lis.forEach((li, i) => {
            const classes = li.className;
            const text = li.textContent?.substring(0, 80) || '';
            const hasChildren = li.children.length > 0;
            if (text.trim()) {
                results.push({index: i, class: classes, text: text, childCount: li.children.length});
            }
        });
        return results.slice(0, 50);
    }""")
    print(f"   📋 Found {len(li_info)} non-empty <li> elements:")
    for info in li_info:
        print(f"      [{info['index']}] class='{info['class']}' children={info['childCount']} text='{info['text']}'")


async def find_sidebar_items(page) -> list:
    """Find sidebar session items strictly under '最近的討論串' section."""
    
    # Find the '最近的討論串' container using evaluate
    section_container = await page.evaluate("""() => {
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {
            if (el.textContent && el.textContent.includes('最近的討論串')) {
                let current = el;
                while (current && current.tagName !== 'BODY') {
                    if (current.nodeType === Node.ELEMENT_NODE) {
                        const classes = current.className || '';
                        if ((typeof classes === 'string' && (classes.includes('sidebar') || classes.includes('drawer') || 
                            classes.includes('u1Qo0b'))) || current.getAttribute('role') === 'navigation') {
                            return current;
                        }
                    }
                    current = current.parentElement || null;
                }
            }
        }
        return null;
    }""")
    
    selectors = [
        '[role="listitem"]:has(.Se0jFd)',
        'div:has(> .Se0jFd)',
        '[role="listitem"]',
    ]
    
    for sel in selectors:
        items = await page.query_selector_all(sel)
        
        if items:
            valid_items = []
            for item in items:
                title_el = await item.query_selector('.Se0jFd')
                if title_el:
                    text = await title_el.inner_text()
                    if text and text.strip() and "最近的討論串" not in text:
                        valid_items.append(item)
            
            if valid_items:
                print(f"   🔍 Found {len(valid_items)} verified session items under '最近的討論串' with selector: {sel}")
                return valid_items, sel

    return [], None


async def find_title_element(element):
    """Find the title element inside a sidebar item using multiple fallback selectors."""
    title_selectors = [
        '.Se0jFd',
        '[class*="title"]',
        'div[class*="text"]',
        'span[class*="text"]',
        'a div',
        'div > div',
    ]
    for sel in title_selectors:
        el = await element.query_selector(sel)
        if el:
            text = await el.inner_text()
            if text and text.strip():
                return el
    # Fallback: get all text content
    return element


async def debug_detect_sessions(page):
    print("🔍 Attempting to detect session titles via JS...")
    items = await page.evaluate("""
        () => {
            const results = [];
            // 抓取所有包含特定文字長度的元素，且看看是否有刪除按鈕特徵的鄰居
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => {
                if (el.children.length === 0 && el.innerText?.trim().length > 5 && el.innerText.length < 100) {
                    const parent = el.parentElement;
                    if (parent && parent.innerText.length < 300) {
                        results.push({
                            text: el.innerText.trim(),
                            tag: el.tagName,
                            class: el.className,
                            parentClass: parent.className
                        });
                    }
                }
            });
            return results.slice(0, 100);
        }
    """)
    # 這裡我們只印出那些看起來像標題的（排除導航欄）
    exclude = ['探索', '更多', '設定', '歷史記錄', '隱私權', '條款', '登入', '管理', '查看']
    count = 0
    for item in items:
        if not any(ex in item['text'] for ex in exclude):
            print(f"   [{count}] {item['text'][:50]} | tag: {item['tag']} | class: {item['class']} | pClass: {item['parentClass']}")
            count += 1
            if count > 30: break

async def run_batch_deletion(delete_queue: list, headless: bool = False, debug: bool = False) -> None:
    """Scan sidebar sessions, match, and delete."""
    
    # ... (existing setup code)
    
    # 執行偵測
    async with async_playwright() as p:
        # 這會在你專案目錄下建立一個名為 user_data 的資料夾來儲存登入狀態
        user_data_dir = os.path.join(os.getcwd(), "user_data")

        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,  # 必須是 False，你才能手動處理第一次登入
            args=["--disable-blink-features=AutomationControlled"]  # 隱藏自動化特徵
        )
        page = context.pages[0] if context.pages else await context.new_page()

        print("🔗 Navigating to Google AI Mode...")
        await page.goto(AI_MODE_URL)

        # Manual Login Check
        if "accounts.google.com" in page.url:
            print("\n🔐 [ACTION REQUIRED] Please log in. Waiting up to 15 mins...")
            await page.wait_for_url(lambda url: "accounts.google.com" not in url, timeout=900000)
            await page.goto(AI_MODE_URL)

        # Wait for page to settle
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(5)
        
        if debug:
            await debug_detect_sessions(page)

        # Try multiple approaches to find sidebar items
        # 1. Try finding with our sidebar selectors first
        session_items, used_sel = await find_sidebar_items(page)
        
        if not session_items:
            print("   ⚠️ No sidebar items found with standard selectors. Trying to open sidebar...")
            
            # Try common sidebar container elements
            sidebar_container_selectors = [
                '[role="navigation"]',
                'div[role="navigation"]',
                '[class*="sidebar"]',
                '[class*="drawer"]',
                '[class*="history"]',
                '[data-ved*="sidebar"]',
                '.rQTE8b',
                '[jsname="DU0NJ"]',
                '[jsname="HJoEPd"]',
            ]
            
            for sel in sidebar_container_selectors:
                container = await page.query_selector(sel)
                if container:
                    print(f"   🔍 Found sidebar container: {sel}")
                    
                    # Try multiple expansion methods
                    # Method 1: Click an expand/collapse button inside the container
                    expand_btn = await container.query_selector('button, a[role="button"], [role="button"], a.ilLN6b')
                    if expand_btn:
                        print("   📂 Expanding sidebar (Method 1)...")
                        try:
                            await expand_btn.evaluate("el => el.click()")
                            await asyncio.sleep(3)
                        except:
                            pass
                    
                    # Method 2: Try clicking on the AI 模式记錄 button directly
                    ai_mode_record_btn = await page.query_selector('a.ilLN6b, a[title="AI 模式記錄"], button[aria-label="AI 模式記錄"][role="button"]')
                    if ai_mode_record_btn:
                        print("   📂 Expanding sidebar (Method 2 - AI 模式記錄)...")
                        try:
                            await ai_mode_record_btn.evaluate("el => el.click()")
                            await asyncio.sleep(3)
                        except:
                            pass
                    
                    break
        
        # Re-try to find sidebar items after any expansion attempts
        session_items, used_sel = await find_sidebar_items(page)
        if not session_items:
            print("   ⚠️ Still no sidebar items found after expansion attempts")
            
            # As a last resort, try to find any elements that might be sidebar items
            # by checking for known title patterns
            print("   🔍 Trying to find elements with potential sidebar titles...")
            potential_items = await page.evaluate("""
                const results = [];
                const elements = document.querySelectorAll('li, [role=\"listitem\"], [class*="sidebar"], [class*="history"], [class*="conversation"]');
                elements.forEach(el => {
                    const text = el.textContent?.trim();
                    if (text && (text.length > 10 && text.length < 200) && 
                        (text.includes('chat') || text.includes('对话') || 
                         text.includes('conversation') || text.includes('history'))) {
                        results.push(el);
                    }
                });
                return results.length;
            """)
            
            if potential_items > 0:
                print(f"   🔍 Found {potential_items} potential sidebar elements in fallback")
            
            await context.close()
            return

        # Debug: dump page structure
        if debug:
            print("\n🔧 DEBUG MODE: Dumping page structure...")
            await dump_page_structure(page, "after_expand")
            session_items, used_sel = await find_sidebar_items(page)
            if not session_items:
                print("   ❌ No sidebar items found with any known selector!")
            await context.close()
            return

        # Find sidebar items with fallback selectors
        session_items, sidebar_selector = await find_sidebar_items(page)
        if not session_items:
            print("   ❌ Could not find sidebar items. Run with debug=True to inspect page structure.")
            await context.close()
            return

        current_queue = list(delete_queue)
        print(f"🚀 Starting scan. Total items in delete queue: {len(current_queue)}")

        processed_titles = set()

        for step in range(1000):  # Increase limit for scrolling
            if not current_queue:
                print("\n🎉 All target items processed!")
                break

            # Re-find items each iteration (DOM may change after deletion)
            session_items, _ = await find_sidebar_items(page)
            if not session_items:
                print("   ⚠️ No sidebar items found, waiting...")
                await asyncio.sleep(3)
                session_items, _ = await find_sidebar_items(page)
                if not session_items:
                    break
            
            target_elem = None
            matched_idx = -1
            matched_title = ""

            for li in session_items:
                title_elem = await find_title_element(li)
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
                    last_title_elem = await find_title_element(last_item)
                    last_title = (await last_title_elem.inner_text()).strip() if last_title_elem else ""
                    print(f"🔄 Scrolling down to load more history... (Last visible: '{last_title[:20]}')")
                    
                    # Scroll to the last item and wait for lazy load
                    await last_item.scroll_into_view_if_needed()
                    await asyncio.sleep(2)  # Wait for API requests
                    
                    # Double check if any new sessions are loaded, if so, continue loop
                    new_session_items, _ = await find_sidebar_items(page)
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
    import sys
    delete_queue = asyncio.run(load_delete_queue("data/delete_queue.json"))
    debug_mode = "--debug" in sys.argv
    asyncio.run(run_batch_deletion(delete_queue, headless=False, debug=debug_mode))
