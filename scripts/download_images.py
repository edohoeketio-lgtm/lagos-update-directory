"""
Download and optimize curated high-resolution photography for all 29 Lagos Updates Directory listings.
Updates data/listings.json and data/directory.db with the local image paths (/img/listings/<slug>.jpg).
"""
import os
import json
import urllib.request
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(BASE_DIR, "img", "listings")
DATA_FILE = os.path.join(BASE_DIR, "data", "listings.json")
DB_FILE = os.path.join(BASE_DIR, "data", "directory.db")

os.makedirs(IMG_DIR, exist_ok=True)

# Curated high-resolution Unsplash images optimized for luxury travel/lifestyle
IMAGE_MAPPINGS = {
    "1": ("the-wheatbaker-hotel", "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80"),
    "2": ("eko-hotel-and-suites", "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80"),
    "3": ("nok-by-alara", "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80"),
    "4": ("chef-tunde-private-kitchen", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80"),
    "5": ("sky-bar-lagos", "https://images.unsplash.com/photo-1519671482749-fd09be7ccebf?auto=format&fit=crop&w=1200&q=80"),
    "6": ("vanguard-protection-services", "https://images.unsplash.com/photo-1508962914676-134849a727f0?auto=format&fit=crop&w=1200&q=80"),
    "7": ("radisson-blu-hotel", "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1200&q=80"),
    "8": ("lagos-continental-hotel", "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80"),
    "9": ("circa-lagos", "https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?auto=format&fit=crop&w=1200&q=80"),
    "10": ("eden-heights-apartments", "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1200&q=80"),
    "11": ("magnolia-suites", "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=1200&q=80"),
    "12": ("harbour-point-residences", "https://images.unsplash.com/photo-1567496898669-ee935f5f647a?auto=format&fit=crop&w=1200&q=80"),
    "13": ("nomad-lagos", "https://images.unsplash.com/photo-1507089947368-19c1da9775ae?auto=format&fit=crop&w=1200&q=80"),
    "14": ("craft-grill", "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80"),
    "15": ("yellow-chilli", "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80"),
    "16": ("escape-lounge-and-bar", "https://images.unsplash.com/photo-1572116469696-31de0f17cc34?auto=format&fit=crop&w=1200&q=80"),
    "17": ("hard-rock-cafe-lagos", "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1200&q=80"),
    "18": ("lagos-clean-ride", "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=1200&q=80"),
    "19": ("firstclass-transfers-ng", "https://images.unsplash.com/photo-1563720223185-11003d516935?auto=format&fit=crop&w=1200&q=80"),
    "20": ("airport-mover-lagos", "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?auto=format&fit=crop&w=1200&q=80"),
    "21": ("lagos-plumbing-pros", "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=1200&q=80"),
    "22": ("coolbreeze-ac-services", "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?auto=format&fit=crop&w=1200&q=80"),
    "23": ("glowup-studio", "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=1200&q=80"),
    "24": ("lagos-dispatch-riders", "https://images.unsplash.com/photo-1558981403-c5f9899a28bc?auto=format&fit=crop&w=1200&q=80"),
    "25": ("sheraton-lagos-hotel", "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=1200&q=80"),
    "26": ("madam-kofo-private-chef", "https://images.unsplash.com/photo-1600565193348-f74bd3c7ccdf?auto=format&fit=crop&w=1200&q=80"),
    "27": ("the-lagos-table", "https://images.unsplash.com/photo-1511795409834-ef04bbd61622?auto=format&fit=crop&w=1200&q=80"),
    "28": ("eagle-eye-security", "https://images.unsplash.com/photo-1485230895905-ec40ba36b9bc?auto=format&fit=crop&w=1200&q=80"),
    "29": ("volt-electrical-ng", "https://images.unsplash.com/photo-1558002038-1055907df827?auto=format&fit=crop&w=1200&q=80"),
}

import ssl
import subprocess

def download_and_update():
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    ssl_context = ssl._create_unverified_context()
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        listings = json.load(f)

    updated_count = 0
    for item in listings:
        item_id = str(item.get("id"))
        if item_id in IMAGE_MAPPINGS:
            slug, url = IMAGE_MAPPINGS[item_id]
            file_name = f"{slug}.jpg"
            file_path = os.path.join(IMG_DIR, file_name)
            relative_url = f"/img/listings/{file_name}"
            
            # Download if not exists or empty
            if not os.path.exists(file_path) or os.path.getsize(file_path) < 1000:
                print(f"Downloading {item['name']} -> {file_name}...")
                success = False
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=15, context=ssl_context) as resp:
                        with open(file_path, "wb") as out:
                            out.write(resp.read())
                    if os.path.getsize(file_path) > 1000:
                        success = True
                except Exception as e:
                    pass

                # If urllib fails, fallback to curl
                if not success:
                    try:
                        subprocess.run(["curl", "-sL", "-A", headers["User-Agent"], url, "-o", file_path], check=True, timeout=20)
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                            success = True
                    except Exception as ce:
                        print(f"  ✗ Curl error: {ce}")

                if success:
                    print(f"  ✓ Saved {file_name} ({os.path.getsize(file_path) // 1024} KB)")
                else:
                    print(f"  ✗ Failed to save {file_name}")
            
            item["image"] = relative_url
            updated_count += 1

    # Save data/listings.json
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2, ensure_ascii=False)
    print(f"Updated {updated_count} listings in {DATA_FILE}")

    # Also update data/directory.db if it exists
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            # Ensure image column exists in listings table
            cur.execute("PRAGMA table_info(listings)")
            cols = [r[1] for r in cur.fetchall()]
            if "image" not in cols:
                cur.execute("ALTER TABLE listings ADD COLUMN image TEXT")
            
            for item in listings:
                if "image" in item:
                    cur.execute("UPDATE listings SET image = ? WHERE id = ?", (item["image"], str(item["id"])))
            conn.commit()
            conn.close()
            print("Successfully updated database directory.db with image paths.")
        except Exception as e:
            print("Notice updating SQLite db:", e)

if __name__ == "__main__":
    download_and_update()
