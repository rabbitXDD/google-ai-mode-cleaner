"""AI Takeout Cleaner - Entry Point Script"""
import sys
import os
import json
import webbrowser
from pathlib import Path

# Add package path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser import parse_takeout_json, save_parsed_items
from ui_generator import generate_review_ui, save_ui_to_file


def compare_and_delete(items: list, output_path: str) -> None:
    """Compare review.html with Takeout JSON and delete unselected items."""
    # Load selected items (what user wants to KEEP)
    with open(output_path, 'r', encoding='utf-8') as f:
        selected_data = json.load(f)

    # selected_items.json exported from review.html has format: {"indices": [...], "total": ..., "keepCount": ...}
    kept_indices = set(selected_data.get("indices", []))

    # Identify items to delete (those NOT in kept_indices)
    delete_queue = []
    for idx, item in enumerate(items):
        if idx not in kept_indices:
            delete_queue.append(item)

    # Save delete queue to JSON for the automation script
    os.makedirs("data", exist_ok=True)
    delete_queue_path = "data/delete_queue.json"
    with open(delete_queue_path, 'w', encoding='utf-8') as f:
        json.dump(delete_queue, f, ensure_ascii=False, indent=2)

    print(f"     ✅ Generated delete queue with {len(delete_queue)} items -> {delete_queue_path}")
    print(f"     ℹ️  Kept {len(kept_indices)} items")


def main():
    """Run takeout parsing and UI generation."""

    # Step 1: Check for input file
    takeout_path = "data/我的活動.json"
    if not os.path.exists(takeout_path):
        print(f" ❌ Input file not found: {takeout_path}")
        print("   Please place your Google Takeout JSON file in the data/ folder")
        sys.exit(1)

    # Step 2: Parse takeout JSON
    print("📄 Parsing takeout JSON...")
    items = parse_takeout_json(takeout_path)
    print(f"     ✅ Parsed {len(items)} AI Mode items")

    # Optional: Save parsed items for reference
    save_parsed_items(items, "data/parsed_items.json")
    print("     💾 Saved to data/parsed_items.json")

    # Step 3: Generate UI
    print("\n📱 Generating UI review page...")
    ui_html = generate_review_ui(items)
    output_path = "review.html"
    save_ui_to_file(ui_html, output_path)
    print(f"     ✅ Review page generated: {output_path}")

    # Step 4: Display instructions
    print("\n📋 Instructions:")
    print("    1. Open review.html in your browser manually")
    print("    2. Review AI Mode items and check 'Keep' for those you want to retain")
    print("    3. Click 'Export Selection & Continue' button (downloads selected_items.json)")
    print("\n   Press Enter when ready to continue:")

    # Auto-open browser
    webbrowser.open('file://' + os.path.abspath(output_path))
    input()

    # Step 5: Compare and export delete queue
    selected_json_path = "selected_items.json"
    if os.path.exists(selected_json_path):
        print("\n🗑️ Generating delete queue...")
        compare_and_delete(items, selected_json_path)
    else:
        print(f"\n⚠️ {selected_json_path} not found. Please export it from review.html first.")

    print("\n✨ Phase 1 Complete!")


if __name__ == '__main__':
    """Run main pipeline."""
    try:
        print("=" * 60)
        print("🚀 AI Mode Takeout Cleaner")
        print("   Phase 1: JSON Parsing + Review UI Generation")
        print("=" * 60)

        main()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)