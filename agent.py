import os
import sys
import anthropic
from dotenv import load_dotenv
from tools import tools, handle_tool_call

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an art scoping assistant helping an artist in New Jersey, USA find opportunities.

When asked for a daily digest:
1. Search for art open calls, residencies, grants, and exhibitions near New Jersey.
2. Use get_opportunity_details on the most promising results.
3. Summarize findings in a clear, scannable digest.
4. Send the digest via send_digest_email.

Always include: opportunity title, organization, deadline (if found), URL, and a 1-sentence description.
"""

DAILY_DIGEST_PROMPT = (
    "Find current art open calls, residencies, grants, and exhibition opportunities "
    "in and around New Jersey, USA. Run at most 3 searches total. Do NOT use "
    "get_opportunity_details. Compile the search results into a short, clear digest "
    "and print it. Do NOT send any email."
)


def run_agent(user_message: str):
    print(f"\nYou: {user_message}")
    print("-" * 40)

    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nAgent: {block.text}")
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n[Using tool: {block.name}]")
                    result = handle_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    # Run `python agent.py --digest` to trigger a daily digest + email
    if len(sys.argv) > 1 and sys.argv[1] == "--digest":
        print("Running daily digest...")
        run_agent(DAILY_DIGEST_PROMPT)
    else:
        print("Art Scoping Agent — type 'quit' to exit")
        print("Tip: run with --digest to trigger a full digest + email\n")
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            if user_input:
                run_agent(user_input)
