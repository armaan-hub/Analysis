
import httpx
import json
import asyncio
import sys

BASE_URL = "http://127.0.0.1:8000"
QUERY = "I have a client who sold Hotel Apartment and now got notice from FTA to pay VAT, need a on pager on this as well documents required to make payment on portal"

async def test_fast_mode():
    print("\n=== Testing Fast Mode (3 turns) ===")
    conv_id = None
    messages = [
        QUERY,
        "What are the specific documents I need to upload to the FTA portal for this payment?",
        "How do I calculate the late payment penalties if the notice was received 3 months after the sale?"
    ]
    
    last_content = None
    for i, msg in enumerate(messages):
        print(f"\nTurn {i+1}: {msg}")
        payload = {
            "message": msg,
            "conversation_id": conv_id,
            "mode": "fast",
            "stream": False
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(f"{BASE_URL}/api/chat/send", json=payload)
                if resp.status_code != 200:
                    print(f"Error ({resp.status_code}): {resp.text}")
                    return None
                data = resp.json()
                conv_id = data["conversation_id"]
                content = data["message"]["content"]
                print(f"Response (len={len(content)}): {content[:100]}...")
                last_content = content
            except Exception as e:
                print(f"Connection error: {e}")
                return None
            
    return last_content

async def test_deep_research_council():
    print("\n=== Testing Deep Research + Council ===")
    
    # Step 1: Deep Research
    print("Running Deep Research...")
    payload = {"query": QUERY}
    base_answer = ""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream("POST", f"{BASE_URL}/api/chat/deep-research", json=payload) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "chunk":
                            base_answer += data["content"]
                        elif data["type"] == "step":
                            print(f"  Step: {data['text']}")
                        elif data["type"] == "error":
                            print(f"  Deep Research Error: {data['text']}")
        except Exception as e:
            print(f"  Connection error in Deep Research: {e}")
    
    print(f"Deep Research Base Answer (len={len(base_answer)}): {base_answer[:100]}...")
    
    if not base_answer:
        print("Skipping Council because base answer is empty.")
        return ""

    # Step 2: Council
    print("\nRunning Council Review...")
    council_payload = {
        "question": QUERY,
        "base_answer": base_answer
    }
    final_answer = ""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream("POST", f"{BASE_URL}/api/chat/council", json=council_payload) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "council_synthesis" and "delta" in data:
                            final_answer += data["delta"]
                        elif data["type"] == "council_expert":
                            if "expert" in data and "status" in data:
                                print(f"  Expert thinking: {data['expert']}")
        except Exception as e:
            print(f"  Connection error in Council: {e}")
    
    print(f"Council Final Answer (len={len(final_answer)}): {final_answer[:100]}...")
    return final_answer

async def test_analyst_council():
    print("\n=== Testing Analyst + Council ===")
    
    # Step 1: Analyst Mode
    print("Running Analyst Mode...")
    payload = {
        "message": QUERY,
        "mode": "analyst",
        "stream": False
    }
    base_answer = ""
    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            resp = await client.post(f"{BASE_URL}/api/chat/send", json=payload)
            if resp.status_code != 200:
                print(f"Analyst Mode Error ({resp.status_code}): {resp.text}")
                return ""
            data = resp.json()
            base_answer = data["message"]["content"]
        except Exception as e:
            print(f"Connection error in Analyst Mode: {e}")
            return ""
    
    print(f"Analyst Base Answer (len={len(base_answer)}): {base_answer[:100]}...")
    
    if not base_answer:
        print("Skipping Council because base answer is empty.")
        return ""

    # Step 2: Council
    print("\nRunning Council Review...")
    council_payload = {
        "question": QUERY,
        "base_answer": base_answer
    }
    final_answer = ""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream("POST", f"{BASE_URL}/api/chat/council", json=council_payload) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "council_synthesis" and "delta" in data:
                            final_answer += data["delta"]
                        elif data["type"] == "council_expert":
                            if "expert" in data and "status" in data:
                                print(f"  Expert thinking: {data['expert']}")
        except Exception as e:
            print(f"  Connection error in Council: {e}")
    
    print(f"Council Final Answer (len={len(final_answer)}): {final_answer[:100]}...")
    return final_answer

async def main():
    try:
        fast_res = await test_fast_mode()
        deep_res = await test_deep_research_council()
        analyst_res = await test_analyst_council()
        
        print("\n=== Summary of Results ===")
        print(f"Fast Mode Success: {fast_res is not None}")
        print(f"Deep Research + Council Success: {deep_res != ''}")
        print(f"Analyst + Council Success: {analyst_res != ''}")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
