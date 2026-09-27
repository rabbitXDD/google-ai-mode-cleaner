# AI Mode Takeout Cleaner

A tool to review, filter, and automatically delete unwanted Google Takeout AI Mode search prompts from Google My Activity.

## Features
- **Data Parsing**: Unescapes Unicode sequences from Google Takeout JSON files.
- **Human-in-the-loop**: Allows manual review of conversations before deletion.
- **Automation**: Uses Playwright to safely delete selected items from the Google My Activity portal.
- **Safe Execution**: Includes "Dry Run" capabilities to verify deletion lists.

## Quick Start
1.  **Export Data**: Download your AI activity from Google Takeout.
2.  **Setup**: Install dependencies using `pip install -r requirements.txt`.
3.  **Run**: Follow the instructions in `docs/plan.md` to parse and process your activity file.

## Project Documentation
- [Specs](docs/specs.md): Technical specifications.
- [Summary](docs/summary.md): Architecture, lessons learned, and implementation guidelines.

---
*Note: This tool requires a headful browser session to maintain authentication state with Google.*
