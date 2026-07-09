import asyncio
import json
import uuid
import httpx

async def run_e2e():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        print(f"\\n--- [EVIDENCE] E2E: Registering User ---")
        user_suffix = str(uuid.uuid4())[:8]
        username = f"e2e_{user_suffix}"
        res = await client.post("/api/v1/auth/register", json={
            "email": f"{username}@example.com",
            "username": username,
            "password": "password"
        })
        print(res.status_code)
        
        print(f"\\n--- [EVIDENCE] E2E: Logging In ---")
        res = await client.post("/api/v1/auth/login", json={
            "username_or_email": username,
            "password": "password"
        })
        token = res.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        
        print(f"\\n--- [EVIDENCE] E2E: Creating Custom Template ---")
        system_prompt = "You are a data extraction assistant. You only output valid JSON. Do not include any explanations or markdown blocks."
        prompt_template = "Extract the key entities from this text into a JSON array of objects with keys 'entity' and 'type'.\\n\\nText: {transcript}\\n\\nOutput only JSON:"
        
        payload = {
            "name": "JSON Extractor",
            "system_prompt": system_prompt,
            "prompt_template": prompt_template
        }
        res = await client.post("/api/v1/templates/", json=payload)
        print(f"Response Status: {res.status_code}")
        print(f"Response Body: {json.dumps(res.json(), indent=2)}")
        template_id = res.json()["id"]
        
        print(f"\\n--- [EVIDENCE] E2E: Running Summarization ---")
        summarize_payload = {
            "transcript": "John Doe from Acme Corp said that the new Q3 revenue numbers look promising for their new product the SuperWidget. Jane Smith agreed and wants a followup next Tuesday.",
            "task": "summarize",
            "model": "qwen3:1.7b",
            "stream": False,
            "custom_template_id": template_id
        }
        print(f"Request Payload: {json.dumps(summarize_payload, indent=2)}")
        res = await client.post("/api/v1/summarization/process", json=summarize_payload, timeout=60.0)
        print(f"Response Status: {res.status_code}")
        print(f"Response Body: {json.dumps(res.json(), indent=2)}")

if __name__ == "__main__":
    asyncio.run(run_e2e())
