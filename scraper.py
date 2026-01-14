from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
import time
import os
import re

class PianoSheetsScraper:
    def __init__(self):
        print("🚀 Initializing Chrome WebDriver...")
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # WebDriver Manager ile otomatik ChromeDriver kurulumu
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        self.base_url = "https://www.onlinepianist.com"
        self.sheets_data = []
        print("✅ WebDriver initialized successfully!")
    
    def get_all_songs(self):
        """Tüm şarkıları topla"""
        print("\n📋 Fetching all songs...")
        url = f"{self.base_url}/songs"
        self.driver.get(url)
        
        # Sayfanın yüklenmesini bekle
        time.sleep(3)
        
        # Scroll yaparak lazy loading'i tetikle
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        max_scrolls = 20  # Maksimum scroll sayısı
        
        while scroll_count < max_scrolls:
            # Sayfanın sonuna scroll yap
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Yeni yüksekliği kontrol et
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            
            last_height = new_height
            scroll_count += 1
            print(f"  Scrolling... ({scroll_count}/{max_scrolls})")
        
        # Sayfanın HTML'ini al
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Şarkı linklerini bul
        song_links = soup.find_all('a', href=re.compile(r'/songs/[^/]+$'))
        
        songs = []
        for link in song_links:
            song_url = link.get('href')
            if song_url and song_url not in [s['url'] for s in songs]:
                # Tam URL oluştur
                if not song_url.startswith('http'):
                    song_url = self.base_url + song_url
                
                # Şarkı adını link text'inden veya URL'den al
                song_name = link.get_text(strip=True)
                if not song_name:
                    song_name = song_url.split('/')[-1].replace('-', ' ').title()
                
                songs.append({
                    'name': song_name,
                    'url': song_url
                })
        
        print(f"✅ Found {len(songs)} songs")
        return songs
    
    def scrape_song_details(self, song_url):
        """Bir şarkının detaylarını çek"""
        try:
            print(f"\n🎵 Scraping: {song_url}")
            self.driver.get(song_url)
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Şarkı adı
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Artist
            artist_elem = soup.find('h2') or soup.find('span', class_='artist')
            artist = artist_elem.get_text(strip=True) if artist_elem else "Unknown"
            
            # Zorluk seviyesi
            difficulty_elem = soup.find('span', class_='difficulty') or soup.find('div', class_='difficulty')
            difficulty = difficulty_elem.get_text(strip=True) if difficulty_elem else "Unknown"
            
            # Thumbnail/Cover image
            img_elem = soup.find('img', class_='song-cover') or soup.find('img', src=re.compile(r'cover|thumb'))
            thumbnail = img_elem.get('src') if img_elem else None
            if thumbnail and not thumbnail.startswith('http'):
                thumbnail = self.base_url + thumbnail
            
            # Rating
            rating_elem = soup.find('span', class_='rating') or soup.find('div', class_='rating')
            rating = rating_elem.get_text(strip=True) if rating_elem else None
            
            # Views/Plays
            views_elem = soup.find('span', class_='views') or soup.find('span', class_='plays')
            views = views_elem.get_text(strip=True) if views_elem else None
            
            song_data = {
                'title': title,
                'artist': artist,
                'url': song_url,
                'difficulty': difficulty,
                'thumbnail': thumbnail,
                'rating': rating,
                'views': views,
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            print(f"  ✅ {title} by {artist}")
            return song_data
            
        except Exception as e:
            print(f"  ❌ Error scraping {song_url}: {str(e)}")
            return None
    
    def save_data(self, filename='piano_sheets.json'):
        """Verileri JSON dosyasına kaydet"""
        print(f"\n💾 Saving data to {filename}...")
        
        # Varolan veriyi yükle
        existing_data = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except:
                pass
        
        # Yeni veriyi ekle (duplicate kontrol)
        existing_urls = [item['url'] for item in existing_data]
        new_count = 0
        
        for sheet in self.sheets_data:
            if sheet['url'] not in existing_urls:
                existing_data.append(sheet)
                new_count += 1
        
        # Kaydet
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Data saved! Total: {len(existing_data)} songs ({new_count} new)")
        
        # README güncelle
        self.update_readme(len(existing_data))
    
    def update_readme(self, total_songs):
        """README.md dosyasını güncelle"""
        print("\n📝 Updating README.md...")
        
        readme_content = f"""# 🎹 Piano Sheets Database

Automatically scraped piano sheet music database from OnlinePianist.

## 📊 Statistics

- **Total Songs**: {total_songs}
- **Last Updated**: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Source**: [OnlinePianist](https://www.onlinepianist.com)

## 📁 Data Structure
```json
{{
  "title": "Song Title",
  "artist": "Artist Name",
  "url": "https://www.onlinepianist.com/songs/...",
  "difficulty": "Easy/Medium/Hard",
  "thumbnail": "https://...",
  "rating": "4.5/5",
  "views": "1.2M",
  "scraped_at": "2024-01-15 12:00:00"
}}
```

## 🔄 Auto-Update

This database is automatically updated every 6 hours via GitHub Actions.

## 📜 License

Data scraped for educational purposes only.
"""
        
        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print("✅ README.md updated!")
    
    def run(self, max_songs=50):
        """Ana scraping işlemini çalıştır"""
        try:
            print("\n" + "="*50)
            print("🎹 PIANO SHEETS SCRAPER STARTED")
            print("="*50)
            
            # Tüm şarkıları al
            songs = self.get_all_songs()
            
            # İlk N şarkıyı scrape et
            songs_to_scrape = songs[:max_songs]
            print(f"\n🎯 Scraping first {len(songs_to_scrape)} songs...")
            
            for i, song in enumerate(songs_to_scrape, 1):
                print(f"\n[{i}/{len(songs_to_scrape)}]", end=" ")
                song_data = self.scrape_song_details(song['url'])
                
                if song_data:
                    self.sheets_data.append(song_data)
                
                # Rate limiting
                time.sleep(1)
            
            # Verileri kaydet
            self.save_data()
            
            print("\n" + "="*50)
            print("✅ SCRAPING COMPLETED SUCCESSFULLY!")
            print("="*50)
            
        except Exception as e:
            print(f"\n❌ Fatal error: {str(e)}")
            raise
        
        finally:
            print("\n🔒 Closing browser...")
            self.driver.quit()
            print("✅ Browser closed!")

if __name__ == "__main__":
    scraper = PianoSheetsScraper()
    scraper.run(max_songs=100)  # İlk 100 şarkıyı scrape et
