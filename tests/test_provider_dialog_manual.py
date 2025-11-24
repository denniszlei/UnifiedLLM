"""Test script for provider dialog functionality."""
import httpx
import asyncio

API_BASE = "http://localhost:8000/api"

async def test_provider_dialog():
    """Test the provider dialog functionality."""
    async with httpx.AsyncClient() as client:
        print("Testing Provider Dialog Functionality")
        print("=" * 50)
        
        # Test 1: Test connection with invalid credentials
        print("\n1. Testing connection with invalid credentials...")
        try:
            response = await client.post(
                f"{API_BASE}/providers/test",
                json={
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "api_key": "invalid-key",
                    "channel_type": "openai"
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 400:
                print(f"   ✓ Correctly rejected invalid credentials")
                print(f"   Error: {response.json()['detail']}")
            else:
                print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Test 2: Add a provider with validation
        print("\n2. Testing add provider with validation...")
        try:
            response = await client.post(
                f"{API_BASE}/providers",
                json={
                    "name": "Test Provider",
                    "base_url": "https://api.test.com/v1/chat/completions",
                    "api_key": "sk-test-key-12345",
                    "channel_type": "openai"
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code in [201, 400]:
                result = response.json()
                if response.status_code == 201:
                    print(f"   ✓ Provider added successfully")
                    print(f"   Provider ID: {result['id']}")
                    print(f"   Masked API Key: {result['api_key_masked']}")
                    provider_id = result['id']
                else:
                    print(f"   ✓ Validation error (expected): {result['detail']}")
                    provider_id = None
            else:
                print(f"   ✗ Unexpected status: {response.status_code}")
                print(f"   Response: {response.text}")
                provider_id = None
        except Exception as e:
            print(f"   ✗ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            provider_id = None
        
        # Test 3: List providers
        print("\n3. Testing list providers...")
        try:
            response = await client.get(f"{API_BASE}/providers")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                providers = response.json()
                print(f"   ✓ Found {len(providers)} provider(s)")
                for p in providers:
                    print(f"     - {p['name']}: {p['api_key_masked']}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Test 4: Update provider (if we created one)
        if provider_id:
            print(f"\n4. Testing update provider (ID: {provider_id})...")
            try:
                response = await client.put(
                    f"{API_BASE}/providers/{provider_id}",
                    json={
                        "name": "Updated Test Provider",
                        "channel_type": "anthropic"
                    }
                )
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✓ Provider updated successfully")
                    print(f"   New name: {result['name']}")
                    print(f"   New channel: {result['channel_type']}")
                else:
                    print(f"   Response: {response.json()}")
            except Exception as e:
                print(f"   ✗ Error: {e}")
            
            # Test 5: Delete provider
            print(f"\n5. Testing delete provider (ID: {provider_id})...")
            try:
                response = await client.delete(f"{API_BASE}/providers/{provider_id}")
                print(f"   Status: {response.status_code}")
                if response.status_code == 204:
                    print(f"   ✓ Provider deleted successfully")
                else:
                    print(f"   Response: {response.text}")
            except Exception as e:
                print(f"   ✗ Error: {e}")
        
        # Test 6: Validation - missing required fields
        print("\n6. Testing validation - missing required fields...")
        try:
            response = await client.post(
                f"{API_BASE}/providers",
                json={
                    "name": "Incomplete Provider"
                    # Missing base_url and api_key
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 422:
                print(f"   ✓ Correctly rejected incomplete data")
                errors = response.json()['detail']
                print(f"   Validation errors: {len(errors)} field(s)")
            else:
                print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        print("\n" + "=" * 50)
        print("Provider Dialog Tests Complete!")

if __name__ == "__main__":
    asyncio.run(test_provider_dialog())
