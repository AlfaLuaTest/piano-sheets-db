#!/usr/bin/env python3
"""
PlayPianoSheets Auto Scraper for GitHub Actions
Automatically scrapes Hard difficulty piano sheets and saves to GitHub
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time
import os
import re
from datetime import datetime

class PianoSheetsScraper:
    def __init__(self):
        # Setup headless Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.base_url = "https://playpianosheets.com"
        
        # Load existing songs to avoid re-scraping
        self.existing_songs = self.load_existing_songs()
        
    def load_existing_songs(self):
        """Load already scraped song IDs from sheets directory"""
        existing = set()
        
        if os.path.exists('sheets'):
            for root, dirs, files in os.walk('sheets'):
                for file in files:
                    if file.endswith('.json'):
                        try:
                            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                existing.add(data.get('id'))
                        except:
                            pass
        
        print(f"📚 Found {len(existing)} existing songs in database")
        return existing
    
    def get_all_song_links(self):
        """Collect all song URLs from the site"""
        print("\n🔍 Collecting song URLs...")
        all_songs = []
        page = 1
        
        while True:
            url = f"{self.base_url}/category/all" + (f"/page/{page}" if page > 1 else "")
            
            try:
                self.driver.get(url)
                time.sleep(2)
                
                # Find all song links
                links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/sheets/"]')
                
                if not links:
                    break
                
                page_songs = []
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        
                        # Skip non-song links
                        if not href or 'category' in href or 'page' in href:
                            continue
                        
                        song_id = href.split('/')[-1]
                        
                        # Skip if already scraped
                        if song_id in self.existing_songs:
                            continue
                        
                        # Extract title and artist
                        try:
                            title = link.find_element(By.CSS_SELECTOR, 'h3, .title').text.strip()
                        except:
                            title = "Unknown"
                        
                        try:
                            artist = link.find_element(By.CSS_SELECTOR, 'p, .artist').text.strip()
                        except:
                            artist = "Unknown"
                        
                        song_data = {
                            'id': song_id,
                            'url': href,
                            'title': title,
                            'artist': artist
                        }
                        
                        # Avoid duplicates
                        if not any(s['id'] == song_id for s in all_songs):
                            all_songs.append(song_data)
                            page_songs.append(song_data)
                    
                    except Exception as e:
                        continue
                
                print(f"  Page {page}: Found {len(page_songs)} new songs (Total new: {len(all_songs)})")
                
                # Check for next page
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, 'a[rel="next"]')
                    page += 1
                except:
                    break
                    
            except Exception as e:
                print(f"  ❌ Error on page {page}: {e}")
                break
        
        print(f"\n✅ Total new songs to scrape: {len(all_songs)}")
        return all_songs
    
    def click_hard_button(self):
        """Click the Hard difficulty button"""
        try:
            # Wait for buttons to load
            time.sleep(1)
            
            # Find Hard button by text
            buttons = self.driver.find_elements(By.TAG_NAME, 'button')
            
            for button in buttons:
                if 'hard' in button.text.lower():
                    button.click()
                    time.sleep(1)
                    print("    ✓ Clicked Hard button")
                    return True
            
            print("    ⚠️  Hard button not found, using default")
            return False
            
        except Exception as e:
            print(f"    ⚠️  Could not click Hard button: {e}")
            return False
    
    def extract_notes(self):
        """Extract notes from the sheet area"""
        try:
            # Try multiple selectors
            selectors = [
                'div.space-y-4',
                'div[class*="space-y"]',
                'pre',
                'code',
                '.sheet-content'
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        text = element.text
                        
                        # Check if it contains piano notation
                        if '[' in text and ']' in text and len(text) > 50:
                            # Clean the notes
                            notes = self.clean_notes(text)
                            if notes:
                                return notes
                
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"    ❌ Error extracting notes: {e}")
            return None
    
    def clean_notes(self, text):
        """Clean and format notes"""
        try:
            # Remove instructions and metadata
            text = re.sub(r'TRANS.*$', '', text, flags=re.MULTILINE | re.DOTALL)
            text = re.sub(r'Speed:.*$', '', text, flags=re.MULTILINE)
            text = re.sub(r'Auto Play.*$', '', text, flags=re.MULTILINE)
            text = re.sub(r'How to Play.*$', '', text, flags=re.MULTILINE | re.DOTALL)
            text = re.sub(r'Sustain.*$', '', text, flags=re.MULTILINE)
            text = re.sub(r'Reset.*$', '', text, flags=re.MULTILINE)
            
            # Remove empty lines and trim
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            
            # Verify it's valid notation
            if '[' in text and ']' in text and len(text) > 20:
                return text
            
            return None
            
        except:
            return None
    
    def scrape_song(self, song):
        """Scrape a single song"""
        try:
            print(f"  🎵 {song['title']} by {song['artist']}")
            
            # Navigate to song page
            self.driver.get(song['url'])
            time.sleep(3)
            
            # Click Hard button
            self.click_hard_button()
            
            # Extract notes
            notes = self.extract_notes()
            
            if not notes:
                print("    ❌ No notes found")
                return False
            
            # Create song data
            song_data = {
                'id': song['id'],
                'title': song['title'],
                'artist': song['artist'],
                'url': song['url'],
                'difficulty': 'hard',
                'notes': notes,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }
            
            # Save to file
            success = self.save_song(song_data)
            
            if success:
                print(f"    ✅ Saved ({len(notes)} chars)")
                return True
            else:
                print("    ❌ Save failed")
                return False
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False
    
    def save_song(self, song_data):
        """Save song to JSON file"""
        try:
            # Clean artist and title for filename
            safe_artist = re.sub(r'[^\w\s-]', '', song_data['artist'])
            safe_artist = safe_artist.strip().replace(' ', '_')
            if not safe_artist:
                safe_artist = 'Unknown'
            
            safe_title = re.sub(r'[^\w\s-]', '', song_data['title'])
            safe_title = safe_title.strip().replace(' ', '_')
            if not safe_title:
                safe_title = song_data['id']
            
            # Create directory structure
            artist_dir = os.path.join('sheets', safe_artist)
            os.makedirs(artist_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(artist_dir, f"{safe_title}.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(song_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"    ❌ Save error: {e}")
            return False
    
    def run(self):
        """Main scraping process"""
        print("=" * 60)
        print("🎹 PlayPianoSheets Auto Scraper")
        print("=" * 60)
        
        try:
            # Get all new songs
            songs = self.get_all_song_links()
            
            if not songs:
                print("\n✅ No new songs to scrape. Database is up to date!")
                return
            
            # Scrape each song
            print(f"\n📝 Starting to scrape {len(songs)} songs...\n")
            
            successful = 0
            failed = 0
            
            for i, song in enumerate(songs, 1):
                print(f"[{i}/{len(songs)}]", end=" ")
                
                if self.scrape_song(song):
                    successful += 1
                else:
                    failed += 1
                
                # Rate limiting
                time.sleep(2)
            
            # Summary
            print("\n" + "=" * 60)
            print("📊 SCRAPING SUMMARY")
            print("=" * 60)
            print(f"✅ Successful: {successful}")
            print(f"❌ Failed: {failed}")
            print(f"📁 Total songs in database: {len(self.existing_songs) + successful}")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            raise
        
        finally:
            self.driver.quit()


if __name__ == "__main__":
    scraper = PianoSheetsScraper()
    scraper.run()
