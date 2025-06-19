from flask import Flask, jsonify, request, render_template
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask_cors import CORS
from cryptography.fernet import Fernet
import time
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Encryption setup
key = Fernet.generate_key()  # In production, store this securely in environment variables
cipher_suite = Fernet(key)

# CSV storage configuration
CSV_FILENAME = 'scraped_data.csv'
CSV_BACKUP_FOLDER = 'backups'

# Create backups folder if it doesn't exist
if not os.path.exists(CSV_BACKUP_FOLDER):
    os.makedirs(CSV_BACKUP_FOLDER)

# Predefined URLs for popular sites
POPULAR_SITES = {
    'WBB': 'https://books.toscrape.com/catalogue/category/books/travel_2/index.html',
    'Deep 6GB': 'https://books.toscrape.com/catalogue/category/books/mystery_3/index.html',
    'Devi 0.9GB': 'https://books.toscrape.com/catalogue/category/books/historical-fiction_4/index.html',
    'Design': 'https://books.toscrape.com/catalogue/category/books/art_25/index.html',
    'E-commerce': 'https://books.toscrape.com/catalogue/category/books/default_15/index.html',
    'News': 'https://books.toscrape.com/catalogue/category/books/nonfiction_13/index.html'
}

def scrape_books(soup, base_url):
    """Scrape book data from BeautifulSoup object"""
    books = []
    
    # For category pages with multiple books
    if soup.select('article.product_pod'):
        for article in soup.select('article.product_pod'):
            try:
                title = article.select_one('h3 a')['title']
                price = article.select_one('p.price_color').get_text(strip=True)
                rating = article.select_one('p.star-rating')['class'][1] + ' stars'
                availability = article.select_one('p.instock').get_text(strip=True) if article.select_one('p.instock') else 'Out of stock'
                image_path = article.img['src'].replace('../..', '')
                image_url = urljoin(base_url, image_path)
                
                books.append({
                    'title': title,
                    'price': price,
                    'rating': rating,
                    'availability': availability,
                    'image_url': image_url
                })
            except Exception as e:
                app.logger.warning(f"Skipping malformed book entry: {str(e)}")
                continue
    
    # For single product pages
    elif soup.select_one('#product_gallery'):
        try:
            product = soup.select_one('.product_main')
            title = product.select_one('h1').get_text(strip=True)
            price = product.select_one('p.price_color').get_text(strip=True)
            rating = product.select_one('p.star-rating')['class'][1] + ' stars'
            availability = product.select_one('p.instock').get_text(strip=True) if product.select_one('p.instock') else 'Out of stock'
            image_path = soup.select_one('#product_gallery img')['src'].replace('../..', '')
            image_url = urljoin(base_url, image_path)
            
            books.append({
                'title': title,
                'price': price,
                'rating': rating,
                'availability': availability,
                'image_url': image_url
            })
        except Exception as e:
            app.logger.error(f"Error processing single product: {str(e)}")
    
    return books

def save_to_csv(data, source_url):
    """Save scraped data to CSV with timestamp and source information"""
    try:
        # Add metadata to each book record
        for book in data:
            book['scrape_timestamp'] = datetime.now().isoformat()
            book['source_url'] = source_url
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Check if file exists to determine write mode
        file_exists = os.path.exists(CSV_FILENAME)
        
        # Save to main CSV file
        df.to_csv(
            CSV_FILENAME,
            mode='a' if file_exists else 'w',
            index=False,
            header=not file_exists
        )
        
        # Create a timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{CSV_BACKUP_FOLDER}/scraped_data_{timestamp}.csv"
        df.to_csv(backup_filename, index=False)
        
        return True
    except Exception as e:
        app.logger.error(f"Failed to save data to CSV: {str(e)}")
        return False

def encrypt_data(data):
    """Encrypt sensitive data before storage/transmission"""
    if isinstance(data, str):
        data = data.encode()
    return cipher_suite.encrypt(data).decode()

def decrypt_data(encrypted_data):
    """Decrypt encrypted data"""
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

def analyze_with_ai(content):
    """Analyze scraped content with ML model (placeholder implementation)"""
    try:
        # Example: Simple sentiment analysis
        positive_words = ['great', 'excellent', 'good', 'awesome']
        negative_words = ['poor', 'bad', 'terrible', 'awful']
        
        content_lower = content.lower()
        positive_score = sum(1 for word in positive_words if word in content_lower)
        negative_score = sum(1 for word in negative_words if word in content_lower)
        score = positive_score - negative_score
        
        return {
            'sentiment': 'positive' if score > 0 else 'negative' if score < 0 else 'neutral',
            'score': score,
            'positive_words': positive_score,
            'negative_words': negative_score,
            'analysis': 'Basic sentiment analysis completed'
        }
    except Exception as e:
        app.logger.error(f"AI analysis failed: {str(e)}")
        return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    """Handle scraping requests with feature card functionality"""
    try:
        start_time = time.time()
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
            
        url = data.get('url', '').strip()
        features = data.get('features', {})
        
        # Handle popular site shortcuts
        if url in POPULAR_SITES:
            url = POPULAR_SITES[url]
        elif url in POPULAR_SITES.values():
            url = url
        
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        if 'books.toscrape.com' not in url:
            return jsonify({
                'error': 'This demo only supports books.toscrape.com URLs',
                'supported_sites': list(POPULAR_SITES.keys())
            }), 400

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            return jsonify({
                'error': f'Failed to fetch URL: {str(e)}',
                'suggestion': 'Check the URL and try again'
            }), 400

        soup = BeautifulSoup(response.text, 'html.parser')
        books = []
        base_url = '/'.join(url.split('/')[:3])
        
        # Scrape book data
        books = scrape_books(soup, base_url)
        
        if not books:
            return jsonify({
                'error': 'No book data found on this page',
                'suggestion': 'Try a books.toscrape.com category page'
            }), 404

        # Save data to CSV
        save_success = save_to_csv(books, url)
        if not save_success:
            app.logger.warning("Data scraping succeeded but CSV save failed")

        # Apply feature card functionalities
        processing_time = time.time() - start_time
        result = {
            'books': books,
            'source': url,
            'count': len(books),
            'processing_time': f"{processing_time:.2f} seconds",
            'features': {
                'speed': features.get('speed', False),
                'ai': features.get('ai', False),
                'security': features.get('security', False)
            },
            'storage': {
                'saved_to_csv': save_success,
                'filename': CSV_FILENAME if save_success else None
            }
        }

        # Apply AI analysis if enabled
        if features.get('ai'):
            for book in books:
                book['ai_analysis'] = analyze_with_ai(book['title'] + " " + book.get('description', ''))
            result['ai_enabled'] = True

        # Apply encryption if enabled
        if features.get('security'):
            for book in books:
                book['title'] = encrypt_data(book['title'])
                book['price'] = encrypt_data(book['price'])
            result['encryption_enabled'] = True

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"Scraping error: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred',
            'details': str(e)
        }), 500

@app.route('/popular-sites', methods=['GET'])
def get_popular_sites():
    return jsonify({
        'sites': POPULAR_SITES,
        'message': 'Use these shortcuts or provide full books.toscrape.com URLs'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)