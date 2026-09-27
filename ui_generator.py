"""AI Takeout Cleaner - UI Generator Module"""
import json


def generate_review_ui(items):
    """Generate HTML review page with checkboxes for each item."""
    
    # Generate item rows
    item_rows = ""
    for idx, item in enumerate(items):
        # Use display_title (extracted from actual prompt) as title, fallback to original
        title_text = item.get('display_title', item.get('original_title', 'Untitled'))
        summary_text = item.get('summary', '')
        time_text = item.get('time', '')

        # 控制預覽長度
        preview_text = summary_text[:150] + "..." if len(summary_text) > 150 else summary_text

        # 安全地進行 HTML 轉義
        html_title = title_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html_preview = preview_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # 渲染卡片
        item_rows += f'<div class="item-row" data-index="{idx}">'
        item_rows += f'<input type="checkbox" id="keep_{idx}">'
        item_rows += f'<label for="keep_{idx}" class="checkbox-label">Keep</label>'
        item_rows += f'<span class="timestamp">{time_text}</span>'
        item_rows += f'<div class="title">{html_title}</div>'
        item_rows += f'<div class="preview">{html_preview}</div>'
        # 添加 last prompt 信息
        if item.get('last_prompt'):
            item_rows += f'<div class="prompt-note">Last prompt: {item["last_prompt"][:80]}</div>'
        item_rows += '</div>\n'
    
    # Build complete HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Mode Takeout Review</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
.header {{ position: sticky; top: 0; background: white; padding: 15px 20px; border-bottom: 2px solid #ddd; z-index: 100; display: flex; justify-content: space-between; align-items: center; }}
.counter {{ font-size: 18px; color: #333; }}
.counter strong {{ color: #2e7d32; }}
.item-row {{ background: white; padding: 15px 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: all 0.2s; }}
.item-row:hover {{ box-shadow: 0 2px 6px rgba(0,0,0,0.15); }}
.item-row.selected {{ background: #e8f5e9; border-left: 4px solid #2e7d32; }}
.checkbox-label {{ font-weight: bold; color: #666; cursor: pointer; margin-right: 10px; }}
.timestamp {{ font-size: 12px; color: #888; margin-bottom: 5px; }}
.title {{ font-weight: bold; color: #1e3a8a; margin-bottom: 8px; font-size: 16px; }} /* ✨ 顏色加深，字體放大加粗 */
.preview {{ font-size: 14px; color: #4b5563; max-height: 80px; overflow: hidden; background: #f9fafb; padding: 10px; border-radius: 6px; border-left: 3px solid #d1d5db; }}
.bulk-actions {{ position: sticky; top: 70px; background: white; padding: 10px 20px; border-bottom: 1px solid #eee; margin-top: -15px; z-index: 90; display: flex; gap: 10px; }}
.bulk-actions button {{ padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s; }}
.btn-select-all {{ background: #f5f5f5; color: #333; }}
.btn-select-all:hover {{ background: #eee; }}
.submit-btn {{ float: right; padding: 12px 24px; background: #2e7d32; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 500; transition: all 0.2s; }}
.submit-btn:hover {{ background: #1b5e20; transform: scale(1.02); box-shadow: 0 2px 8px rgba(46,125,50,0.3); }}
.search-box {{ padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; width: 300px; margin-right: 10px; font-size: 14px; }}
</style>
</head>
<body>
<div class="header">
<h2>📋 AI Mode Takeout Review</h2>
<div class="counter">Kept: <strong id="keep-count">0</strong> / Total: <strong id="total-count">{len(items)}</strong></div>
</div>

<div class="bulk-actions">
<input type="text" class="search-box" placeholder="Search prompts..." id="search-box">
<button class="btn-select-all" onclick="selectAll()">Select All</button>
<button class="btn-select-all" onclick="deselectAll()">Deselect All</button>
<button class="submit-btn" onclick="exportSelection()">✅ Export Selection & Continue</button>
</div>

<div id="items-container">
{item_rows}
</div>

<script>
let keepCount = 0;
const totalCount = {len(items)};

document.querySelectorAll('.item-row').forEach(row => {{
// 修改點擊事件：避免點到 checkbox 本身時連續觸發兩次變換
row.addEventListener('click', function(e) {{ 
    if(e.target.tagName !== 'INPUT' && e.target.tagName !== 'LABEL') {{
        this.querySelector('input').click(); 
    }}
}});

row.querySelector('input').addEventListener('change', function(e) {{
if (this.checked) {{
this.closest('.item-row').classList.add('selected');
keepCount++;
}} else {{
this.closest('.item-row').classList.remove('selected');
keepCount--;
}}
updateCounter();
}});
}});

function selectAll() {{
document.querySelectorAll('.item-row input[type="checkbox"]').forEach(cb => {{
if(!cb.checked) {{
cb.checked = true;
cb.closest('.item-row').classList.add('selected');
keepCount++;
}}
}});
updateCounter();
}}

function deselectAll() {{
document.querySelectorAll('.item-row input[type="checkbox"]').forEach(cb => {{
if(cb.checked) {{
cb.checked = false;
cb.closest('.item-row').classList.remove('selected');
keepCount--;
}}
}});
updateCounter();
}}

function updateCounter() {{
document.getElementById('keep-count').textContent = keepCount;
}}

document.getElementById('search-box').addEventListener('input', function(e) {{
const searchTerm = e.target.value.toLowerCase();
document.querySelectorAll('.item-row').forEach(row => {{
const title = row.querySelector('.title').textContent.toLowerCase();
const preview = row.querySelector('.preview').textContent.toLowerCase();
if (title.includes(searchTerm) || preview.includes(searchTerm)) {{
row.style.display = '';
}} else {{
row.style.display = 'none';
}}
}});
}});

function exportSelection() {{
const selectedIndices = [];
document.querySelectorAll('.item-row input[type="checkbox"]:checked').forEach(cb => {{
selectedIndices.push(parseInt(cb.closest('.item-row').dataset.index));
}});

const dataJson = JSON.stringify({{indices: selectedIndices, total: totalCount, keepCount: keepCount}}, null, 2);
const blob = new Blob([dataJson], {{ type: 'application/json' }});
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = 'selected_items.json';
a.click();

alert(`Exported ${{keepCount}} items!\nNext step: Run Playwright automation.`);
}}

updateCounter();
</script>
</body>
</html>'''
    
    return html


def save_ui_to_file(html, output_path):
    """Save UI HTML to file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


if __name__ == '__main__':
    test_items = [
         {'index': 0, 'title': 'Test Query 1', 'time': '2026-09-12T09:00:00.000Z', 
          'preview': "Your prompt: Test Query 1 \\n Search's response: First test preview text...", 'full_html': ''},
    ]
    html = generate_review_ui(test_items)
    with open('test_ui.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ Test UI generated: test_ui.html")
