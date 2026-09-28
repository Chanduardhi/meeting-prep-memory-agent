import os
import sys
import time
import shutil
import warnings
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from groq import Groq
from hindsight_client import Hindsight

# Ignore non-critical async cleanup warnings on shutdown
warnings.filterwarnings("ignore", category=ResourceWarning)

# API Keys and Endpoint Configuration
GROQ_KEY = "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"
HINDSIGHT_KEY = "hsk_206d86d484ff68016576cf1f1e50d8e8_71ac1203c7359c28"
BASE_URL = "https://api.hindsight.vectorize.io"

# Initialize API Clients
groq_client = Groq(api_key=GROQ_KEY)
hindsight = Hindsight(base_url=BASE_URL, api_key=HINDSIGHT_KEY)

# Memory Bank Identifier for Hindsight
BANK_ID = "alex_nexuscorp_memory"

# Directories for Auto-Watcher
DEBRIEFS_DIR = "debriefs"
SYNCED_DIR = os.path.join(DEBRIEFS_DIR, "synced")

# Ensure directories exist
os.makedirs(DEBRIEFS_DIR, exist_ok=True)
os.makedirs(SYNCED_DIR, exist_ok=True)


def retain_meeting_notes(notes: str, source_name: str = "Manual Entry"):
    """Store meeting debriefs into Hindsight memory bank."""
    print(f"\n[Hindsight] Syncing memory from '{source_name}'...")
    hindsight.retain(
        bank_id=BANK_ID,
        content=notes
    )
    print(f"[Hindsight] Memory synced successfully from '{source_name}'!")


def generate_prep_brief(query: str) -> str:
    """Recall client context from Hindsight and generate a structured executive brief using Groq."""
    print(f"\n[Hindsight] Recalling memories for query: '{query}'...")
    
    memories = hindsight.recall(
        bank_id=BANK_ID,
        query=query
    )
    
    context_text = "\n".join([f"- {m}" for m in memories]) if memories else "No context found."

    system_prompt = f"""You are an Executive Meeting Prep Assistant.
Your job is to prevent missing promises, repeated questions, forgotten preferences, and wasted prep time.

RECALLED CLIENT MEMORIES:
{context_text}

Based on these recalled memories, format a concise pre-meeting briefing into:
1. Communication Preferences
2. Promises / Commitments Made
3. Action Items & Key Discussion Topics
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message.content


def process_debrief_file(filepath: str):
    """Reads a text file, syncs its content to Hindsight, and moves it to the synced archive."""
    if not (filepath.endswith(".txt") or filepath.endswith(".md")):
        return

    # Brief delay to allow file writing to finish
    time.sleep(1)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content:
            filename = os.path.basename(filepath)
            retain_meeting_notes(content, source_name=filename)
            
            # Archive processed file
            dest_path = os.path.join(SYNCED_DIR, filename)
            shutil.move(filepath, dest_path)
            print(f"[Auto-Watcher] Archived {filename} -> {SYNCED_DIR}/\n")
    except Exception as e:
        print(f"[Auto-Watcher ERROR] Could not process {filepath}: {e}")


def sync_existing_files():
    """Syncs any pre-existing files in the debriefs folder upon startup."""
    for filename in os.listdir(DEBRIEFS_DIR):
        filepath = os.path.join(DEBRIEFS_DIR, filename)
        if os.path.isfile(filepath):
            process_debrief_file(filepath)


class DebriefFolderHandler(FileSystemEventHandler):
    """Watchdog handler that triggers whenever a file is created or modified in debriefs/."""
    def on_created(self, event):
        if not event.is_directory:
            process_debrief_file(event.src_path)


def main_interactive():
    print("=" * 60)
    print("  Meeting Prep Agent + Folder Auto-Watcher")
    print("=" * 60)
    print(f"[Auto-Watcher Active] Drop .txt/.md files into '{DEBRIEFS_DIR}/' to auto-sync.")

    # 1. Sync any existing files in debriefs/ directory
    sync_existing_files()

    # 2. Start background folder watcher
    event_handler = DebriefFolderHandler()
    observer = Observer()
    observer.schedule(event_handler, path=DEBRIEFS_DIR, recursive=False)
    observer.start()

    try:
        while True:
            print("\nOptions:")
            print("1. Generate prep briefing for a contact")
            print("2. Manually paste new meeting notes")
            print("3. Exit")
            
            choice = input("\nSelect an option (1-3): ").strip()

            if choice == "1":
                contact = input("\nEnter contact or company name (e.g., Sarah Jenkins): ").strip()
                if contact:
                    query = f"Brief me on {contact} before our upcoming call."
                    briefing = generate_prep_brief(query)
                    print("\n" + "=" * 60)
                    print("             EXECUTIVE PREP BRIEFING")
                    print("=" * 60)
                    print(briefing)
                    print("=" * 60)

            elif choice == "2":
                print("\nEnter/paste meeting notes below (type 'DONE' on a new line when finished):")
                lines = []
                while True:
                    line = input()
                    if line.strip().upper() == "DONE":
                        break
                    lines.append(line)
                
                text = "\n".join(lines).strip()
                if text:
                    retain_meeting_notes(text, source_name="Terminal Input")

            elif choice == "3":
                print("Stopping folder watcher and exiting...")
                break

    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main_interactive()
    sys.exit(0)
