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

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'name': 'Piano Sheets API',
        'version': '1.0.0',
        'description': 'API for accessing Roblox piano sheets from playpianosheets.com',
        'source': 'https://github.com/AlfaLuaTest/piano-sheets-db',
        'endpoints': {
            'GET /': 'API information',
            'GET /api/songs': 'Get all songs (title, artist, url)',
            'GET /api/songs/full': 'Get all songs with complete data',
            'GET /api/song/<id>': 'Get specific song by ID',
            'GET /api/search?q=query': 'Search songs by title or artist',
            'GET /api/categories': 'Get all available categories',
            'GET /api/category/<name>': 'Get songs by category',
            'GET /api/stats': 'Get database statistics',
            'GET /api/random': 'Get a random song'
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
        'id': s.get('url', '').split('/')[-1]
    } for s in songs]
    
    return jsonify({
        'count': len(simplified),
        'songs': simplified
    })

@app.route('/api/songs/full', methods=['GET'])
def get_songs_full():
    """Return complete data for all songs"""
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
    ╔══════════════════════════════════════╗
    ║   🎹 Piano Sheets API Server        ║
    ╠══════════════════════════════════════╣
    ║   Port: {port}                     ║
    ║   Debug: {debug}                   ║
    ║   Repository: {GITHUB_REPO}        ║
    ╚══════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
