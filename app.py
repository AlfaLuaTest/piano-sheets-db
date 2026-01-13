from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from github import Github
from datetime import datetime

app = Flask(__name__)
CORS(app)

# GitHub Configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'username/piano-sheets')
GITHUB_BRANCH = 'main'

# Initialize GitHub client
g = Github(GITHUB_TOKEN) if GITHUB_TOKEN else None
repo = g.get_repo(GITHUB_REPO) if g else None

class PianoSheetsScraper:
    BASE_URL = "https://playpianosheets.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_all_songs(self):
        """Fetch all songs from the category page"""
        songs = []
        page = 1
        
        while True:
            try:
                url = f"{self.BASE_URL}/category/all/page/{page}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code != 200:
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                song_items = soup.find_all('a', class_='sheet-item') or soup.find_all('div', class_='song-item')
                
                if not song_items:
                    break
                
                for item in song_items:
                    try:
                        link = item.get('href', '')
                        title_elem = item.find('h3') or item.find('div', class_='title')
                        artist_elem = item.find('p', class_='artist') or item.find('div', class_='artist')
                        
                        if link and title_elem:
                            songs.append({
                                'title': title_elem.text.strip(),
                                'artist': artist_elem.text.strip() if artist_elem else 'Unknown',
                                'url': link if link.startswith('http') else f"{self.BASE_URL}{link}",
                                'id': link.split('/')[-1]
                            })
                    except Exception as e:
                        print(f"Error parsing song item: {e}")
                        continue
                
                page += 1
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break
        
        return songs
    
    def get_sheet_notes(self, song_url, difficulty='hard'):
        """Extract sheet notes from a song page"""
        try:
            response = self.session.get(song_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the sheet container
            sheet_container = soup.find('div', class_='sheet-container') or soup.find('pre', class_='sheet')
            
            if not sheet_container:
                # Try alternative selectors
                sheet_container = soup.find('code') or soup.find('textarea')
            
            if sheet_container:
                notes = sheet_container.text.strip()
                
                # Clean up the notes
                notes = re.sub(r'\s+', ' ', notes)  # Remove extra whitespace
                notes = notes.replace(' - ', '-')  # Fix rest notation
                
                return notes
            
            return None
            
        except Exception as e:
            print(f"Error fetching sheet: {e}")
            return None
    
    def save_to_github(self, song_data, notes):
        """Save song notes to GitHub repository"""
        if not repo:
            return False
        
        try:
            # Create filename
            safe_title = re.sub(r'[^\w\s-]', '', song_data['title']).strip().replace(' ', '_')
            safe_artist = re.sub(r'[^\w\s-]', '', song_data['artist']).strip().replace(' ', '_')
            filename = f"sheets/{safe_artist}/{safe_title}.json"
            
            # Prepare content
            content = {
                'id': song_data['id'],
                'title': song_data['title'],
                'artist': song_data['artist'],
                'url': song_data['url'],
                'notes': notes,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            json_content = json.dumps(content, indent=2, ensure_ascii=False)
            
            # Check if file exists
            try:
                file = repo.get_contents(filename, ref=GITHUB_BRANCH)
                repo.update_file(
                    filename,
                    f"Update {song_data['title']}",
                    json_content,
                    file.sha,
                    branch=GITHUB_BRANCH
                )
            except:
                repo.create_file(
                    filename,
                    f"Add {song_data['title']}",
                    json_content,
                    branch=GITHUB_BRANCH
                )
            
            return True
            
        except Exception as e:
            print(f"Error saving to GitHub: {e}")
            return False

scraper = PianoSheetsScraper()

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'endpoints': {
            'GET /api/songs': 'Get all available songs',
            'GET /api/song/<id>': 'Get specific song details',
            'POST /api/scrape': 'Trigger scraping (protected)',
            'GET /api/search?q=query': 'Search songs',
            'GET /api/stats': 'Get statistics'
        }
    })

@app.route('/api/songs', methods=['GET'])
def get_songs():
    """Return list of all available songs from GitHub"""
    try:
        if not repo:
            return jsonify({'error': 'GitHub not configured'}), 500
        
        contents = repo.get_contents("sheets", ref=GITHUB_BRANCH)
        songs = []
        
        for artist_folder in contents:
            if artist_folder.type == "dir":
                artist_songs = repo.get_contents(artist_folder.path, ref=GITHUB_BRANCH)
                for song_file in artist_songs:
                    if song_file.name.endswith('.json'):
                        try:
                            content = json.loads(song_file.decoded_content.decode())
                            songs.append({
                                'id': content.get('id'),
                                'title': content.get('title'),
                                'artist': content.get('artist'),
                                'path': song_file.path
                            })
                        except:
                            continue
        
        return jsonify({
            'count': len(songs),
            'songs': songs
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/song/<song_id>', methods=['GET'])
def get_song(song_id):
    """Get specific song with notes"""
    try:
        if not repo:
            return jsonify({'error': 'GitHub not configured'}), 500
        
        # Search for song file
        contents = repo.get_contents("sheets", ref=GITHUB_BRANCH)
        
        for artist_folder in contents:
            if artist_folder.type == "dir":
                artist_songs = repo.get_contents(artist_folder.path, ref=GITHUB_BRANCH)
                for song_file in artist_songs:
                    if song_file.name.endswith('.json'):
                        try:
                            content = json.loads(song_file.decoded_content.decode())
                            if content.get('id') == song_id:
                                return jsonify(content)
                        except:
                            continue
        
        return jsonify({'error': 'Song not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['GET'])
def search_songs():
    """Search songs by title or artist"""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        if not repo:
            return jsonify({'error': 'GitHub not configured'}), 500
        
        contents = repo.get_contents("sheets", ref=GITHUB_BRANCH)
        results = []
        
        for artist_folder in contents:
            if artist_folder.type == "dir":
                artist_songs = repo.get_contents(artist_folder.path, ref=GITHUB_BRANCH)
                for song_file in artist_songs:
                    if song_file.name.endswith('.json'):
                        try:
                            content = json.loads(song_file.decoded_content.decode())
                            title = content.get('title', '').lower()
                            artist = content.get('artist', '').lower()
                            
                            if query in title or query in artist:
                                results.append({
                                    'id': content.get('id'),
                                    'title': content.get('title'),
                                    'artist': content.get('artist'),
                                    'notes': content.get('notes')
                                })
                        except:
                            continue
        
        return jsonify({
            'query': query,
            'count': len(results),
            'results': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scrape', methods=['POST'])
def scrape_sheets():
    """Trigger scraping process (protected endpoint)"""
    # Simple API key protection
    api_key = request.headers.get('X-API-Key')
    if api_key != os.environ.get('SCRAPER_API_KEY'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get all songs
        songs = scraper.get_all_songs()
        
        scraped_count = 0
        failed = []
        
        for song in songs:
            try:
                notes = scraper.get_sheet_notes(song['url'])
                if notes:
                    if scraper.save_to_github(song, notes):
                        scraped_count += 1
                    else:
                        failed.append(song['title'])
                time.sleep(2)  # Rate limiting
            except Exception as e:
                failed.append(f"{song['title']}: {str(e)}")
                continue
        
        return jsonify({
            'status': 'completed',
            'total_songs': len(songs),
            'scraped': scraped_count,
            'failed': failed
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get repository statistics"""
    try:
        if not repo:
            return jsonify({'error': 'GitHub not configured'}), 500
        
        contents = repo.get_contents("sheets", ref=GITHUB_BRANCH)
        total_songs = 0
        artists = set()
        
        for artist_folder in contents:
            if artist_folder.type == "dir":
                artists.add(artist_folder.name)
                artist_songs = repo.get_contents(artist_folder.path, ref=GITHUB_BRANCH)
                total_songs += len([f for f in artist_songs if f.name.endswith('.json')])
        
        return jsonify({
            'total_songs': total_songs,
            'total_artists': len(artists),
            'last_updated': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
