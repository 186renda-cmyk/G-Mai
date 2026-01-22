import os
import glob
import re
from bs4 import BeautifulSoup, Comment
import datetime
import json

# Configuration
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(ROOT_DIR, 'index.html')
BLOG_DIR = os.path.join(ROOT_DIR, 'blog')
DOMAIN = "https://g-mai.top"

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def normalize_link(url):
    """
    Removes .html suffix from internal links.
    """
    if not url:
        return url
    
    # Skip external, data, mailto, etc.
    if url.startswith(('http://', 'https://', 'mailto:', 'tel:', 'data:')):
        return url
    
    # Internal link
    if url.endswith('.html'):
        return url[:-5]
    if '.html#' in url:
        return url.replace('.html#', '#')
    return url

def clean_links_in_soup(soup):
    """
    Normalizes all links in the given soup.
    """
    for a in soup.find_all('a', href=True):
        a['href'] = normalize_link(a['href'])
    return soup

def get_favicons(soup):
    """
    Extracts favicon links and ensures they are root-relative.
    """
    favicons = []
    # Select all icon related links
    for rel in ['icon', 'shortcut icon', 'apple-touch-icon']:
        for link in soup.find_all('link', rel=rel):
            # Create a copy to not modify the original immediately
            new_link = BeautifulSoup(str(link), 'html.parser').link
            href = new_link.get('href', '')
            if href and not href.startswith(('http', 'data:')) and not href.startswith('/'):
                 new_link['href'] = '/' + href
            favicons.append(new_link)
    return favicons

def prepare_component_for_subpages(component):
    """
    Adjusts links in a component (Nav/Footer) for use in subpages.
    e.g. #products -> /#products
    """
    new_comp = BeautifulSoup(str(component), 'html.parser').find(component.name)
    for a in new_comp.find_all('a', href=True):
        href = a['href']
        if href.startswith('#'):
            a['href'] = '/' + href
    return new_comp

def collect_blog_posts():
    """
    Scans blog directory for articles.
    Returns a list of dicts with metadata.
    """
    posts = []
    files = glob.glob(os.path.join(BLOG_DIR, '*.html'))
    for file_path in files:
        filename = os.path.basename(file_path)
        if filename == 'index.html':
            continue
            
        content = read_file(file_path)
        soup = BeautifulSoup(content, 'html.parser')
        
        # Title cleanup
        raw_title = soup.title.string if soup.title else filename
        title = raw_title.split('|')[0].strip()
        
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        description = desc_tag['content'] if desc_tag else ''
        
        date_str = ''
        time_tag = soup.find('time')
        if time_tag and time_tag.has_attr('datetime'):
            date_str = time_tag['datetime']
        else:
            # Fallback: Search for date pattern in text
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', content)
            if date_match:
                date_str = date_match.group(0)
        
        posts.append({
            'path': file_path,
            'filename': filename,
            'url': f'/blog/{filename.replace(".html", "")}',
            'title': title,
            'description': description,
            'date': date_str
        })
    
    # Sort by date descending
    posts.sort(key=lambda x: x['date'] if x['date'] else '0000-00-00', reverse=True)
    return posts

def generate_schema(metadata, type='WebPage', posts=None):
    """
    Generates JSON-LD schema based on metadata and type.
    """
    schema = {
        "@context": "https://schema.org",
        "@graph": []
    }
    
    # Organization
    org = {
        "@type": "Organization",
        "@id": f"{DOMAIN}/#organization",
        "name": "G-Mai.TOP",
        "url": DOMAIN,
        "logo": {
            "@type": "ImageObject",
            "url": f"{DOMAIN}/logo.png" # Placeholder or extract from index
        }
    }
    schema["@graph"].append(org)
    
    # WebSite
    website = {
        "@type": "WebSite",
        "@id": f"{DOMAIN}/#website",
        "url": DOMAIN,
        "name": "G-Mai.TOP",
        "publisher": {"@id": f"{DOMAIN}/#organization"}
    }
    schema["@graph"].append(website)
    
    # Main Entity
    if type == 'BlogPosting':
        entity = {
            "@type": "BlogPosting",
            "headline": metadata['title'].split('|')[0].strip(),
            "description": metadata['description'],
            "datePublished": metadata.get('date', ''),
            "dateModified": metadata.get('date', ''), 
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": metadata['canonical']
            },
            "author": {
                "@type": "Organization",
                "name": "G-Mai Team"
            },
            "publisher": {"@id": f"{DOMAIN}/#organization"}
        }
        schema["@graph"].append(entity)
    elif type == 'CollectionPage':
        entity = {
            "@type": "CollectionPage",
            "@id": metadata['canonical'],
            "url": metadata['canonical'],
            "name": metadata['title'],
            "description": metadata['description'],
            "isPartOf": {"@id": f"{DOMAIN}/#website"}
        }
        schema["@graph"].append(entity)
        
        # Add ItemList for CollectionPage
        if posts:
            item_list = {
                "@type": "ItemList",
                "itemListElement": []
            }
            for i, post in enumerate(posts):
                item_list["itemListElement"].append({
                    "@type": "ListItem",
                    "position": i + 1,
                    "url": f"{DOMAIN}{post['url']}",
                    "name": post['title']
                })
            schema["@graph"].append(item_list)
            
    else:
        # Generic WebPage
        entity = {
            "@type": "WebPage",
            "@id": metadata['canonical'],
            "url": metadata['canonical'],
            "name": metadata['title'],
            "description": metadata['description'],
            "isPartOf": {"@id": f"{DOMAIN}/#website"}
        }
        schema["@graph"].append(entity)
        
    # BreadcrumbList
    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "首页",
                "item": DOMAIN
            }
        ]
    }
    
    # Add current page to breadcrumb
    if type == 'BlogPosting':
        breadcrumb["itemListElement"].append({
            "@type": "ListItem",
            "position": 2,
            "name": "博客",
            "item": f"{DOMAIN}/blog/"
        })
        breadcrumb["itemListElement"].append({
            "@type": "ListItem",
            "position": 3,
            "name": metadata['title'].split('|')[0].strip(),
            "item": metadata['canonical']
        })
    elif 'blog' in metadata['canonical']:
         breadcrumb["itemListElement"].append({
            "@type": "ListItem",
            "position": 2,
            "name": "博客",
            "item": f"{DOMAIN}/blog/"
        })
    else:
        # Root level pages
        breadcrumb["itemListElement"].append({
            "@type": "ListItem",
            "position": 2,
            "name": metadata['title'].split('|')[0].strip(),
            "item": metadata['canonical']
        })
        
    schema["@graph"].append(breadcrumb)
    
    return json.dumps(schema, ensure_ascii=False, indent=2)

def update_article_head(soup, metadata, favicons, schema_type='WebPage', posts=None):
    """
    Reconstructs the head section.
    """
    head = soup.head
    if not head:
        return

    # Extract existing useful tags to preserve
    preserved_tags = []
    
    # We want to preserve styles and scripts that are NOT standard meta
    # And specifically NOT the ones we are regenerating
    for child in head.children:
        if child.name in ['script', 'style', 'link']:
            rel = child.get('rel', [])
            if isinstance(rel, list): rel = rel[0] if rel else ''
            
            # Skip regenerated tags
            if child.name == 'link' and (rel in ['icon', 'shortcut icon', 'apple-touch-icon', 'canonical', 'alternate']):
                continue
            
            # Keep CSS
            if child.name == 'link' and rel == 'stylesheet':
                preserved_tags.append(child)
            # Keep Style
            elif child.name == 'style':
                preserved_tags.append(child)
            # Keep Scripts but SKIP JSON-LD as we regenerate it
            elif child.name == 'script':
                 if child.get('type') == 'application/ld+json':
                     continue
                 preserved_tags.append(child)

    # Clear head
    head.clear()
    
    # Group A: Basic Metadata
    head.append(soup.new_tag('meta', charset="UTF-8"))
    head.append(soup.new_tag('meta', attrs={'name': "viewport", 'content': "width=device-width, initial-scale=1.0"}))
    
    title_tag = soup.new_tag('title')
    title_tag.string = metadata['title']
    head.append(title_tag)
    
    # Group B: SEO Core
    if metadata.get('description'):
        head.append(soup.new_tag('meta', attrs={'name': "description", 'content': metadata['description']}))
    if metadata.get('keywords'):
        head.append(soup.new_tag('meta', attrs={'name': "keywords", 'content': metadata['keywords']}))
    
    canonical = soup.new_tag('link', rel="canonical", href=metadata['canonical'])
    head.append(canonical)
    
    # Group C: Indexing & Geo
    head.append(soup.new_tag('meta', attrs={'name': "robots", 'content': "index, follow"}))
    
    meta_lang = soup.new_tag('meta')
    meta_lang['http-equiv'] = "content-language"
    meta_lang['content'] = "zh-CN"
    head.append(meta_lang)
    
    for lang, url in metadata['hreflangs'].items():
        link = soup.new_tag('link', rel="alternate", hreflang=lang, href=url)
        head.append(link)
        
    # Group D: Branding & Resources
    for fav in favicons:
        head.append(fav)
        
    for tag in preserved_tags:
        head.append(tag)
        
    # Group E: Schema
    schema_script = soup.new_tag('script', type="application/ld+json")
    schema_script.string = generate_schema(metadata, schema_type, posts)
    head.append(schema_script)
        
    return soup

def inject_recommendations(soup, current_post_path, all_posts):
    """
    Injects 'Recommended Reading' at the bottom of the article prose.
    """
    article = soup.find('article')
    if not article:
        return
        
    # Locate the prose container
    prose = article.find(class_=lambda x: x and 'prose' in x)
    target_container = prose if prose else article

    # Logic: Pick 2 posts that are NOT the current one
    recommendations = [p for p in all_posts if p['path'] != current_post_path][:2]
    if not recommendations:
        return

    # Create HTML structure
    rec_div = soup.new_tag('div', attrs={'class': "mt-12 pt-8 border-t border-white/10"})
    
    h3 = soup.new_tag('h3', attrs={'class': "text-xl font-bold text-white mb-6 flex items-center gap-2"})
    icon = soup.new_tag('i', attrs={'data-lucide': "book-open", 'class': "w-5 h-5 text-gBlue"})
    h3.append(icon)
    h3.append(" 推荐阅读")
    rec_div.append(h3)
    
    grid = soup.new_tag('div', attrs={'class': "grid grid-cols-1 md:grid-cols-2 gap-4"})
    
    for rec in recommendations:
        a = soup.new_tag('a', href=rec['url'], attrs={'class': "block p-4 rounded-xl bg-white/5 border border-white/10 hover:border-gYellow/50 hover:bg-white/10 transition-all group"})
        
        div_label = soup.new_tag('div', attrs={'class': "text-xs text-gray-500 mb-1"})
        div_label.string = "Guide"
        a.append(div_label)
        
        div_title = soup.new_tag('div', attrs={'class': "font-bold text-white group-hover:text-gYellow transition-colors"})
        div_title.string = rec['title']
        a.append(div_title)
        
        grid.append(a)
        
    rec_div.append(grid)
    
    # Remove existing recommendations if present
    # Heuristic: h3 containing 'Recommended Reading' or '推荐阅读'
    for child in target_container.find_all('div', recursive=False):
        if child.find('h3') and re.search(r'推荐阅读|Recommended Reading', child.find('h3').get_text()):
            child.decompose()
            
    target_container.append(rec_div)

def create_card_node(soup, post):
    """
    Creates a card node for the post list.
    """
    a = soup.new_tag('a', href=post['url'], attrs={'class': "group flex flex-col h-full bg-[#111] border border-white/10 rounded-2xl overflow-hidden hover:border-gBlue/50 hover:shadow-2xl hover:shadow-gBlue/10 hover:-translate-y-1 transition-all duration-300"})
    
    # Image part
    div_img = soup.new_tag('div', attrs={'class': "h-48 relative overflow-hidden bg-gray-900"})
    div_bg = soup.new_tag('div', attrs={'class': "absolute inset-0 bg-gradient-to-br from-gray-900 to-black"})
    div_img.append(div_bg)
    
    # Glow effect
    div_glow = soup.new_tag('div', attrs={'class': "absolute inset-0 opacity-20 group-hover:opacity-30 transition-opacity duration-500 bg-[radial-gradient(circle_at_50%_120%,#4285F4,transparent_70%)]"})
    div_img.append(div_glow)
    
    # Icon
    icon_container = soup.new_tag('div', attrs={'class': "absolute inset-0 flex items-center justify-center"})
    icon = soup.new_tag('i', attrs={'data-lucide': "file-text", 'class': "w-16 h-16 text-white/20 group-hover:text-gBlue group-hover:scale-110 transition-all duration-500"})
    icon_container.append(icon)
    div_img.append(icon_container)
    
    a.append(div_img)
    
    # Content part
    div_content = soup.new_tag('div', attrs={'class': "p-6 flex-1 flex flex-col relative"})
    
    # Date
    div_meta = soup.new_tag('div', attrs={'class': "flex items-center gap-2 mb-3 text-xs font-medium text-gBlue/80"})
    span_date = soup.new_tag('span', attrs={'class': "px-2 py-1 rounded-md bg-gBlue/10 border border-gBlue/20"})
    span_date.string = post['date'] if post['date'] else "Guide"
    div_meta.append(span_date)
    div_content.append(div_meta)
    
    # Title
    h3 = soup.new_tag('h3', attrs={'class': "text-xl font-bold text-white mb-3 group-hover:text-gBlue transition-colors leading-snug"})
    h3.string = post['title']
    div_content.append(h3)
    
    # Desc
    p = soup.new_tag('p', attrs={'class': "text-sm text-gray-400 line-clamp-2 mb-6 flex-1 leading-relaxed"})
    p.string = post['description']
    div_content.append(p)
    
    # Footer
    div_footer = soup.new_tag('div', attrs={'class': "flex items-center justify-between pt-4 border-t border-white/5"})
    span_read = soup.new_tag('span', attrs={'class': "text-sm font-semibold text-white group-hover:text-gBlue transition-colors"})
    span_read.string = "阅读全文"
    div_footer.append(span_read)
    
    arrow_container = soup.new_tag('div', attrs={'class': "w-8 h-8 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-gBlue group-hover:text-white transition-all duration-300"})
    arrow = soup.new_tag('i', attrs={'data-lucide': "arrow-right", 'class': "w-4 h-4"})
    arrow_container.append(arrow)
    div_footer.append(arrow_container)
    
    div_content.append(div_footer)
    
    a.append(div_content)
    return a

def process_static_pages(favicons, nav_for_sub, footer_for_sub):
    """
    Process other static pages in root directory (trust.html, etc.)
    """
    print("Processing Root Static Pages...")
    files = glob.glob(os.path.join(ROOT_DIR, '*.html'))
    for file_path in files:
        filename = os.path.basename(file_path)
        if filename == 'index.html' or 'google' in filename: # Skip index and google verification files
            continue
            
        print(f"Processing {filename}...")
        content = read_file(file_path)
        soup = BeautifulSoup(content, 'html.parser')
        
        # Metadata extraction (simple fallback)
        raw_title = soup.title.string if soup.title else filename
        title = raw_title.split('|')[0].strip()
        
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        description = desc_tag['content'] if desc_tag else ''
        
        url_path = f"/{filename.replace('.html', '')}"
        
        metadata = {
            'title': title + " | G-Mai.TOP",
            'description': description,
            'keywords': soup.find('meta', attrs={'name': 'keywords'})['content'] if soup.find('meta', attrs={'name': 'keywords'}) else "",
            'canonical': f"{DOMAIN}{url_path}",
            'hreflangs': {
                'x-default': f"{DOMAIN}{url_path}",
                'zh': f"{DOMAIN}{url_path}",
                'zh-CN': f"{DOMAIN}{url_path}"
            }
        }
        
        # 1. Update Head
        update_article_head(soup, metadata, favicons, schema_type='WebPage')
        
        # 2. Layout Sync
        if soup.nav: soup.nav.replace_with(nav_for_sub.__copy__())
        elif soup.body: soup.body.insert(0, nav_for_sub.__copy__())
            
        if soup.footer: soup.footer.replace_with(footer_for_sub.__copy__())
        elif soup.body: soup.body.append(footer_for_sub.__copy__())
            
        # 3. Clean Links
        clean_links_in_soup(soup)
        
        write_file(file_path, soup.prettify())

def main():
    print("Phase 1: Smart Extraction...")
    index_content = read_file(INDEX_PATH)
    index_soup = BeautifulSoup(index_content, 'html.parser')
    
    # Extract Nav and Footer
    nav_component = index_soup.find('nav')
    footer_component = index_soup.find('footer')
    
    # Extract Favicons
    favicons = get_favicons(index_soup)
    
    # Prepare Nav/Footer for subpages (fix #anchors)
    nav_for_sub = prepare_component_for_subpages(nav_component)
    footer_for_sub = prepare_component_for_subpages(footer_component)
    
    # Collect Blog Posts
    print("Collecting Blog Posts...")
    posts = collect_blog_posts()
    
    print("Phase 2 & 3: Processing Blog Posts...")
    for post in posts:
        print(f"Processing {post['filename']}...")
        content = read_file(post['path'])
        soup = BeautifulSoup(content, 'html.parser')
        
        # 1. Head Reconstruction
        metadata = {
            'title': post['title'] + " | G-Mai.TOP",
            'description': post['description'],
            'keywords': soup.find('meta', attrs={'name': 'keywords'})['content'] if soup.find('meta', attrs={'name': 'keywords'}) else "",
            'canonical': f"{DOMAIN}{post['url']}",
            'hreflangs': {
                'x-default': f"{DOMAIN}{post['url']}",
                'zh': f"{DOMAIN}{post['url']}",
                'zh-CN': f"{DOMAIN}{post['url']}"
            },
            'date': post['date']
        }
        update_article_head(soup, metadata, favicons, schema_type='BlogPosting')
        
        # 2. Layout Sync
        if soup.nav: soup.nav.replace_with(nav_for_sub.__copy__())
        elif soup.body: soup.body.insert(0, nav_for_sub.__copy__())
            
        if soup.footer: soup.footer.replace_with(footer_for_sub.__copy__())
        elif soup.body: soup.body.append(footer_for_sub.__copy__())
            
        # 3. Clean Links
        clean_links_in_soup(soup)
        
        # 4. Inject Recommendations
        inject_recommendations(soup, post['path'], posts)
        
        # Save
        write_file(post['path'], soup.prettify())

    # Process Blog Index (Aggregation Page) if it exists
    blog_index_path = os.path.join(BLOG_DIR, 'index.html')
    if os.path.exists(blog_index_path):
        print("Processing Blog Index...")
        content = read_file(blog_index_path)
        soup = BeautifulSoup(content, 'html.parser')
        
        metadata = {
            'title': "博客文章 | G-Mai.TOP",
            'description': "G-Mai.TOP 博客文章列表，提供谷歌账号使用指南、防封技巧及解决方案。",
            'keywords': "谷歌账号教程, Gmail使用指南, 谷歌账号防封",
            'canonical': f"{DOMAIN}/blog/",
            'hreflangs': {
                'x-default': f"{DOMAIN}/blog/",
                'zh': f"{DOMAIN}/blog/",
                'zh-CN': f"{DOMAIN}/blog/"
            }
        }
        update_article_head(soup, metadata, favicons, schema_type='CollectionPage', posts=posts)
        
        if soup.nav: soup.nav.replace_with(nav_for_sub.__copy__())
        if soup.footer: soup.footer.replace_with(footer_for_sub.__copy__())
        clean_links_in_soup(soup)
        
        # Populate Grid
        main_tag = soup.find('main')
        if main_tag:
            grid = main_tag.find('div', class_=lambda x: x and 'grid' in x) 
            if not grid:
                section = main_tag.find('section')
                if section: grid = section.find('div', class_=lambda x: x and 'grid' in x) or section

            if grid:
                grid.clear()
                for post in posts:
                    card = create_card_node(soup, post)
                    grid.append(card)
        
        write_file(blog_index_path, soup.prettify())

    # Process other static pages in root
    process_static_pages(favicons, nav_for_sub, footer_for_sub)

    print("Phase 4: Global Update (Homepage)...")
    # Update Homepage Blog Section
    blog_section = index_soup.find('section', id='blog')
    if blog_section:
        grid = blog_section.find('div', class_=lambda x: x and 'grid' in x)
        if grid:
            grid.clear()
            # Add top 3 posts
            for post in posts[:3]:
                card = create_card_node(index_soup, post)
                grid.append(card)
    
    # Clean links in Homepage too
    clean_links_in_soup(index_soup)
    
    # Save Index
    write_file(INDEX_PATH, index_soup.prettify())
    
    # Generate Sitemap
    print("Generating Sitemap...")
    generate_sitemap(posts)
    
    print("Build Complete.")

def generate_sitemap(posts):
    """
    Generates sitemap.xml dynamically based on current content.
    """
    sitemap_path = os.path.join(ROOT_DIR, 'sitemap.xml')
    today = datetime.date.today().isoformat()
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Home
    xml.append('    <!-- Home -->')
    xml.append('    <url>')
    xml.append(f'        <loc>{DOMAIN}/</loc>')
    xml.append(f'        <lastmod>{today}</lastmod>')
    xml.append('        <changefreq>daily</changefreq>')
    xml.append('        <priority>1.0</priority>')
    xml.append('    </url>')
    
    # Blog Index
    xml.append('')
    xml.append('    <!-- Blog Index -->')
    xml.append('    <url>')
    xml.append(f'        <loc>{DOMAIN}/blog/</loc>')
    xml.append(f'        <lastmod>{today}</lastmod>')
    xml.append('        <changefreq>daily</changefreq>')
    xml.append('        <priority>0.9</priority>')
    xml.append('    </url>')
    
    # Blog Posts
    xml.append('')
    xml.append('    <!-- Blog Posts -->')
    for post in posts:
        xml.append('    <url>')
        xml.append(f'        <loc>{DOMAIN}{post["url"]}</loc>')
        xml.append(f'        <lastmod>{post["date"] if post["date"] else today}</lastmod>')
        xml.append('        <changefreq>weekly</changefreq>')
        xml.append('        <priority>0.8</priority>')
        xml.append('    </url>')
        
    # Static Pages
    xml.append('')
    xml.append('    <!-- Static Pages -->')
    static_pages = ['trust', 'refund-policy', 'privacy-policy']
    for page in static_pages:
        xml.append('    <url>')
        xml.append(f'        <loc>{DOMAIN}/{page}</loc>')
        xml.append(f'        <lastmod>{today}</lastmod>')
        xml.append('        <changefreq>monthly</changefreq>')
        xml.append('        <priority>0.5</priority>')
        xml.append('    </url>')
        
    xml.append('</urlset>')
    
    write_file(sitemap_path, '\n'.join(xml))

if __name__ == "__main__":
    main()