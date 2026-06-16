import requests

def test_save_advisor():
    base_url = "http://127.0.0.1:8000/api/v1"
    
    # We will try to update Vineet Tiwari (F2-369-107) to rating 4.2 and reviews count 15
    payload = {
        "f2_fintech_id": "F2-369-107",
        "name": "Vineet Tiwari",
        "designation": "Wealth & Investing Expert",
        "avatar_url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=60",
        "availability": "available",
        "expertise": ["Wealth Management", "Equity", "Mutual Funds"],
        "strength": "Portfolio Optimization",
        "bio": "Certified Financial Planner with 8+ years experience",
        "category": "wealth",
        "fee": 999,
        "rating": 4.2,
        "reviews_count": 15
    }
    
    print(f"Sending POST to {base_url}/advisors to update Vineet Tiwari...")
    try:
        r = requests.post(f"{base_url}/advisors", json=payload)
        r.raise_for_status()
        res = r.json()
        print(f"Response: f2_fintech_id={res['f2_fintech_id']}, rating={res['rating']}, reviews_count={res['reviews_count']}")
    except Exception as e:
        print(f"POST request failed: {e}")
        return

    # Verify via GET
    print("\nFetching advisors list to verify...")
    try:
        r = requests.get(f"{base_url}/advisors")
        r.raise_for_status()
        advisors = r.json()
        target = [a for a in advisors if a["f2_fintech_id"] == "F2-369-107"]
        if target:
            adv = target[0]
            print(f"GET response for Vineet Tiwari: rating={adv['rating']}, reviews_count={adv['reviews_count']}")
            if adv['rating'] == 4.2 and adv['reviews_count'] == 15:
                print("PASSED: Rating and reviews count successfully updated in the DB and returned by GET advisors!")
            else:
                print("FAILED: Mismatch in rating or reviews count.")
        else:
            print("Vineet Tiwari not found.")
    except Exception as e:
        print(f"GET request failed: {e}")

if __name__ == "__main__":
    test_save_advisor()
