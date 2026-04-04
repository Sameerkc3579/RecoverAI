import asyncio
import os
import sys

# Hack to allow running within the FastAPI directory structure
sys.path.insert(0, os.path.abspath('.'))

from app.services.nlp_service import process_debtor_reply

async def main():
    test_replies = [
        "bhai 10 din me pakka payment kar dunga, abhi thoda tight hai",
        "tumhara maal kharab tha, koi payment nahi milega jab tak replace nahi karte",
        "sethji abhi gaon gaye hain, aane ke baad check karte hain",
        "I will pay the remaining amount by next friday.",
        "kyu baar baar msg kar rahe ho, dimag kharab mat karo"
    ]

    print("=== EXECUTING RECOVERY NLP PIPELINE ===")
    print("Model: gemini-1.5-flash\n")

    for i, msg in enumerate(test_replies, 1):
        print(f"CASE {i}:")
        print(f"➜ RAW INPUT (Debtor Reply): \"{msg}\"")
        try:
            result = await process_debtor_reply(msg)
            print(f"↳ TRANSLATED ENGLISH: [{result.get('translated_text')}]")
            print(f"↳ INTENT CATCHED:   [{result.get('intent').upper()}]  (Confidence: {result.get('confidence')})")
            print(f"↳ RECOMMENDED STEP: [{result.get('suggested_action')}]\n")
        except Exception as e:
            print(f"ERROR: {e}\n")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
