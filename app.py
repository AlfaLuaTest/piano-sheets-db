from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
from github import Github
from datetime import datetime

app = Flask(__name__)
CORS(app)

# GitHub Configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'AlfaLuaTest/piano-sheets-db')
GITHUB_BRANCH = 'main'
SHEETS_FILE_PATH = 'sheets/piano_sheets.json'
FAVORITES_FILE_PATH = 'data.js'

# Initialize GitHub client
g = Github(GITHUB_TOKEN) if GITHUB_TOKEN else None
repo = g.get_repo(GITHUB_REPO) if g else None

def get_songs_data():
    """Get songs data from GitHub"""
    try:
        if not repo:
            return None, "GitHub not configured"
        
        file = repo.get_contents(SHEETS_FILE_PATH, ref=GITHUB_BRANCH)
        songs = json.loads(file.decoded_content.decode())
        return songs, None
    except Exception as e:
        return None, str(e)

def get_favorites():
    """Get favorites from data.js"""
    try:
        if not repo:
            return [], "GitHub not configured"
        
        file = repo.get_contents(FAVORITES_FILE_PATH, ref=GITHUB_BRANCH)
        content = file.decoded_content.decode()
        
        # Parse JavaScript array
        import re
        match = re.search(r'favorites\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if match:
            favorites_str = match.group(1)
            # Extract quoted strings
            favorites = re.findall(r'"([^"]+)"', favorites_str)
            return favorites, None
        return [], None
    except Exception as e:
        return [], str(e)

def update_favorites(favorites_list):
    """Update favorites in data.js"""
    try:
        if not repo:
            return False, "GitHub not configured"
        
        # Get current file
        file = repo.get_contents(FAVORITES_FILE_PATH, ref=GITHUB_BRANCH)
        
        # Create new content
        favorites_js = ',\n  '.join([f'"{fav}"' for fav in favorites_list])
        new_content = f"""// Auto-generated favorites list
// Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

export const favorites = [
  {favorites_js}
];
"""
        
        # Update file
        repo.update_file(
            FAVORITES_FILE_PATH,
            f"Update favorites ({len(favorites_list)} items)",
            new_content,
            file.sha,
            branch=GITHUB_BRANCH
        )
        
        return True, None
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'name': 'Matcha Piano Sheets API',
        'version': '2.0.0',
        'description': 'API for Matcha Piano Player - Roblox piano sheets from playpianosheets.com',
        'source': 'https://github.com/AlfaLuaTest/piano-sheets-db',
        'endpoints': {
            'GET /': 'API information',
            'GET /api/songs': 'Get all songs (simplified)',
            'GET /api/songs/full': 'Get all songs with sheet music',
            'GET /api/song/<id>': 'Get specific song by ID',
            'GET /api/search?q=query': 'Search songs by title or artist',
            'GET /api/categories': 'Get all available categories',
            'GET /api/category/<name>': 'Get songs by category',
            'GET /api/stats': 'Get database statistics',
            'GET /api/random': 'Get a random song',
            'GET /api/favorites': 'Get user favorites',
            'POST /api/favorites/add': 'Add song to favorites',
            'POST /api/favorites/remove': 'Remove song from favorites',
            'GET /data.js': 'Get favorites as JavaScript module'
        }
    })

@app.route('/api/songs', methods=['GET'])
def get_songs():
    """Return simplified list of all songs"""
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Return simplified list (without sheet content)
    simplified = [{
        'title': s.get('title'),
        'artist': s.get('artist', 'Unknown'),
        'url': s.get('url'),
        'difficulty': s.get('difficulty', 'Normal'),
        'thumbnail': s.get('thumbnail'),
        'id': s.get('url', '').split('/')[-1],
        'categories': s.get('categories', [])
    } for s in songs]
    
    return jsonify({
        'count': len(simplified),
        'songs': simplified
    })

@app.route('/api/songs/full', methods=['GET'])
def get_songs_full():
    """Return complete data for all songs including sheet music"""
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    return jsonify({
        'count': len(songs),
        'songs': songs
    })

@app.route('/api/song/<path:song_id>', methods=['GET'])
def get_song(song_id):
    """Get specific song by ID (from URL slug)"""
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Find song by ID (URL slug)
    for song in songs:
        url = song.get('url', '')
        if song_id in url or url.endswith(f'/{song_id}'):
            return jsonify(song)
    
    return jsonify({'error': 'Song not found'}), 404

@app.route('/api/search', methods=['GET'])
def search_songs():
    """Search songs by title or artist"""
    query = request.args.get('q', '').lower().strip()
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Search in title and artist
    results = []
    for song in songs:
        title = song.get('title', '').lower()
        artist = song.get('artist', '').lower()
        
        if query in title or query in artist:
            results.append(song)
    
    return jsonify({
        'query': query,
        'count': len(results),
        'results': results
    })

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all available categories"""
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Collect unique categories
    categories = set()
    for song in songs:
        for cat in song.get('categories', []):
            categories.add(cat)
    
    return jsonify({
        'count': len(categories),
        'categories': sorted(list(categories))
    })

@app.route('/api/category/<path:category_name>', methods=['GET'])
def get_songs_by_category(category_name):
    """Get songs filtered by category"""
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    # Filter songs by category
    filtered = []
    for song in songs:
        categories = [c.lower() for c in song.get('categories', [])]
        if category_name.lower() in categories:
            filtered.append(song)
    
    return jsonify({
        'category': category_name,
        'count': len(filtered),
        'songs': filtered
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    favorites, _ = get_favorites()
    
    # Collect statistics
    total_songs = len(songs)
    artists = set()
    difficulties = {}
    categories = set()
    total_sheets = 0
    
    for song in songs:
        # Artists
        artist = song.get('artist', 'Unknown')
        if artist and artist != 'Unknown Artist':
            artists.add(artist)
        
        # Difficulties
        difficulty = song.get('difficulty', 'Unknown')
        difficulties[difficulty] = difficulties.get(difficulty, 0) + 1
        
        # Categories
        for cat in song.get('categories', []):
            categories.add(cat)
        
        # Count sheets
        total_sheets += len(song.get('sheets', []))
    
    # Get last update time
    last_updated = None
    if songs:
        last_updated = songs[-1].get('scraped_at')
    
    return jsonify({
        'total_songs': total_songs,
        'total_artists': len(artists),
        'total_categories': len(categories),
        'total_sheets': total_sheets,
        'total_favorites': len(favorites),
        'difficulties': difficulties,
        'last_updated': last_updated,
        'database_file': SHEETS_FILE_PATH,
        'repository': GITHUB_REPO
    })

@app.route('/api/random', methods=['GET'])
def get_random_song():
    """Get a random song"""
    import random
    
    songs, error = get_songs_data()
    
    if error:
        return jsonify({'error': error}), 500
    
    if not songs:
        return jsonify({'error': 'No songs available'}), 404
    
    random_song = random.choice(songs)
    return jsonify(random_song)

@app.route('/api/favorites', methods=['GET'])
def get_favorites_list():
    """Get list of favorite song IDs"""
    favorites, error = get_favorites()
    
    if error:
        return jsonify({'error': error}), 500
    
    return jsonify({
        'count': len(favorites),
        'favorites': favorites
    })

@app.route('/api/favorites/add', methods=['POST'])
def add_favorite():
    """Add a song to favorites"""
    data = request.get_json()
    
    if not data or 'song_id' not in data:
        return jsonify({'error': 'song_id is required'}), 400
    
    song_id = data['song_id']
    
    # Get current favorites
    favorites, error = get_favorites()
    if error:
        return jsonify({'error': error}), 500
    
    # Check if already exists
    if song_id in favorites:
        return jsonify({'message': 'Already in favorites', 'favorites': favorites})
    
    # Add to favorites
    favorites.append(song_id)
    
    # Update file
    success, error = update_favorites(favorites)
    if not success:
        return jsonify({'error': error}), 500
    
    return jsonify({
        'message': 'Added to favorites',
        'count': len(favorites),
        'favorites': favorites
    })

@app.route('/api/favorites/remove', methods=['POST'])
def remove_favorite():
    """Remove a song from favorites"""
    data = request.get_json()
    
    if not data or 'song_id' not in data:
        return jsonify({'error': 'song_id is required'}), 400
    
    song_id = data['song_id']
    
    # Get current favorites
    favorites, error = get_favorites()
    if error:
        return jsonify({'error': error}), 500
    
    # Remove from favorites
    if song_id in favorites:
        favorites.remove(song_id)
        
        # Update file
        success, error = update_favorites(favorites)
        if not success:
            return jsonify({'error': error}), 500
        
        return jsonify({
            'message': 'Removed from favorites',
            'count': len(favorites),
            'favorites': favorites
        })
    else:
        return jsonify({'message': 'Not in favorites', 'favorites': favorites})

@app.route('/data.js', methods=['GET'])
def get_data_js():
    """Serve data.js file directly"""
    favorites, error = get_favorites()
    
    if error:
        favorites = []
    
    favorites_js = ',\n  '.join([f'"{fav}"' for fav in favorites])
    content = f"""// Auto-generated favorites list
// Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

export const favorites = [
  {favorites_js}
];
"""
    
    return content, 200, {'Content-Type': 'application/javascript'}

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║   🎹 Matcha Piano Sheets API Server   ║
    ╠═══════════════════════════════════════╣
    ║   Port: {port}                        ║
    ║   Debug: {debug}                      ║
    ║   Repository: {GITHUB_REPO}           ║
    ╚═══════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
