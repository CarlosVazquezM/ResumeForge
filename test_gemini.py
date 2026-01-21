#!/usr/bin/env python3
"""Quick test to verify gemini-2.5-flash model works."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from resumeforge.providers.google_provider import GoogleProvider

def test_gemini_model(api_key: str | None = None):
    """Test if gemini-2.5-flash works."""
    # Try to get API key from argument, then environment
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        # Try to get from user input
        print("🔑 Google API key not found in environment.")
        api_key = input("Please enter your GOOGLE_API_KEY (or press Ctrl+C to cancel): ").strip()
        if not api_key:
            print("❌ No API key provided")
            return False
    
    print(f"🔑 API key found (length: {len(api_key)}, starts with: {api_key[:10]}...)")
    print(f"🧪 Testing model: gemini-2.5-flash")
    print()
    
    try:
        provider = GoogleProvider(api_key=api_key, model="gemini-2.5-flash")
        print("✅ Provider initialized successfully")
        
        print("📤 Sending test request...")
        response = provider.generate_text(
            prompt="Say 'Hello, World!' in one sentence.",
            system_prompt="You are a helpful assistant.",
            temperature=0.0,
            max_tokens=50
        )
        
        print()
        print(f"✅ Success! Model 'gemini-2.5-flash' works!")
        print(f"📝 Response: {response}")
        return True
        
    except Exception as e:
        print()
        print(f"❌ Error occurred:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {e}")
        
        # Check if it's a model not found error
        error_str = str(e)
        if "404" in error_str or "NOT_FOUND" in error_str or "not found" in error_str.lower():
            print()
            print("💡 This looks like a model not found error.")
            print("   The model name 'gemini-2.5-flash' may not be correct.")
            print("   Try: gemini-1.5-flash-latest or gemini-1.5-flash")
        
        return False

if __name__ == "__main__":
    # Allow API key as command-line argument
    api_key = None
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    
    success = test_gemini_model(api_key)
    sys.exit(0 if success else 1)
