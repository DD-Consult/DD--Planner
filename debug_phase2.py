#!/usr/bin/env python3
"""Debug script to investigate Phase 2 failures"""
import requests
import json

BASE_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Authenticate
response = requests.post(
    f"{API_BASE}/auth/login",
    data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)
access_token = response.json()["access_token"]
headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

print("=" * 80)
print("DEBUG 1: Create proposal and check options structure")
print("=" * 80)

# Create a proposal
response = requests.post(
    f"{API_BASE}/proposals",
    headers=headers,
    json={"client_name": "Debug Test", "proposal_title": "Debug Proposal"}
)
proposal = response.json()
print(f"\nProposal created: {proposal.get('id')}")
print(f"Data keys: {list(proposal.get('data', {}).keys())}")
print(f"\nOptions structure:")
options = proposal.get('data', {}).get('options', [])
for i, opt in enumerate(options):
    print(f"  Option {i}: id={opt.get('id')}, title={opt.get('title')}")

print("\n" + "=" * 80)
print("DEBUG 2: Create template and check options")
print("=" * 80)

response = requests.post(
    f"{API_BASE}/proposal-templates",
    headers=headers,
    json={
        "name": "Debug Template",
        "description": "Debug",
        "from_proposal_id": proposal.get('id')
    }
)
template = response.json()
print(f"\nTemplate created: {template.get('id')}")
print(f"Data keys: {list(template.get('data', {}).keys())}")
print(f"\nOptions structure:")
options = template.get('data', {}).get('options', [])
for i, opt in enumerate(options):
    print(f"  Option {i}: id={opt.get('id')}, title={opt.get('title')}")

print("\n" + "=" * 80)
print("DEBUG 3: Document ingestion with AI")
print("=" * 80)

with open("/tmp/harbour_brief.docx", "rb") as f:
    files = {"file": ("harbour_brief.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"use_ai": "true"}
    headers_upload = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.post(
        f"{API_BASE}/proposals/from-document",
        headers=headers_upload,
        files=files,
        data=data,
        timeout=70
    )

if response.status_code == 200:
    doc_proposal = response.json()
    print(f"\nDocument proposal created: {doc_proposal.get('id')}")
    print(f"Data keys: {list(doc_proposal.get('data', {}).keys())}")
    print(f"Has 'brief': {'brief' in doc_proposal.get('data', {})}")
    print(f"Has 'assistant_message': {'assistant_message' in doc_proposal}")
    
    # Check what's in understanding
    understanding = doc_proposal.get('data', {}).get('understanding', {})
    print(f"\nUnderstanding keys: {list(understanding.keys())}")
    if 'text' in understanding:
        text = understanding['text']
        print(f"Understanding text length: {len(text)}")
        print(f"Understanding text preview: {text[:200]}")
else:
    print(f"ERROR: Status {response.status_code}")
    print(response.text)

print("\n" + "=" * 80)
print("DEBUG 4: Document ingestion without AI")
print("=" * 80)

with open("/tmp/harbour_brief.docx", "rb") as f:
    files = {"file": ("harbour_brief.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"use_ai": "false"}
    headers_upload = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.post(
        f"{API_BASE}/proposals/from-document",
        headers=headers_upload,
        files=files,
        data=data,
        timeout=30
    )

if response.status_code == 200:
    doc_proposal_no_ai = response.json()
    print(f"\nDocument proposal (no AI) created: {doc_proposal_no_ai.get('id')}")
    print(f"Data keys: {list(doc_proposal_no_ai.get('data', {}).keys())}")
    
    # Check understanding
    understanding = doc_proposal_no_ai.get('data', {}).get('understanding', {})
    print(f"\nUnderstanding keys: {list(understanding.keys())}")
    if 'text' in understanding:
        text = understanding['text']
        print(f"Understanding text length: {len(text)}")
        print(f"Understanding text preview: {text[:500]}")
        print(f"Contains 'Harbour Logistics': {'Harbour Logistics' in text}")
else:
    print(f"ERROR: Status {response.status_code}")
    print(response.text)

# Cleanup
print("\n" + "=" * 80)
print("Cleaning up...")
print("=" * 80)
requests.delete(f"{API_BASE}/proposals/{proposal.get('id')}", headers={"Authorization": f"Bearer {access_token}"})
requests.delete(f"{API_BASE}/proposal-templates/{template.get('id')}", headers={"Authorization": f"Bearer {access_token}"})
if 'doc_proposal' in locals():
    requests.delete(f"{API_BASE}/proposals/{doc_proposal.get('id')}", headers={"Authorization": f"Bearer {access_token}"})
if 'doc_proposal_no_ai' in locals():
    requests.delete(f"{API_BASE}/proposals/{doc_proposal_no_ai.get('id')}", headers={"Authorization": f"Bearer {access_token}"})
print("Done")
