#!/usr/bin/env python3
"""Migrates a WordPress WXR export to Eleventy markdown posts."""

import xml.etree.ElementTree as ET
import re
import os
import sys
from markdownify import markdownify as md

if len(sys.argv) < 2:
    print("Usage: python3 migrate-wp.py <export.xml>")
    sys.exit(1)

NS = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'wp': 'http://wordpress.org/export/1.2/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}

FIVEWELLS_BASE = 'https://youknowjack.fivewells.com/archives'


def slugify(s):
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def yaml_str(s):
    if not s:
        return '""'
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def replace_picasa_tables(html):
    """Convert Picasa/Google Photos table embeds to inline image + caption."""
    def _replace(m):
        table_html = m.group(0)
        img_match = re.search(r'<img\s[^>]*src="([^"]+)"', table_html)
        album_match = re.search(
            r'From <a href="([^"]+)">([^<]+)</a>', table_html)
        parts = []
        if img_match:
            src = img_match.group(1)
            if album_match:
                parts.append(
                    f'<p><img src="{src}" /><br/>'
                    f'<em>From <a href="{album_match.group(1)}">'
                    f'{album_match.group(2)}</a></em></p>'
                )
            else:
                parts.append(f'<p><img src="{src}" /></p>')
        elif album_match:
            parts.append(
                f'<p><a href="{album_match.group(1)}">'
                f'{album_match.group(2)}</a></p>'
            )
        return '\n' + ''.join(parts) + '\n'
    return re.sub(r'<table[^>]*>.*?</table>', _replace, html, flags=re.DOTALL)


def wrap_bare_paragraphs(html):
    """Wrap newline-separated paragraphs in <p> tags for posts lacking them."""
    lines = html.split('\n')
    wrapped = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Don't double-wrap block elements that are already self-contained
        if re.match(r'^<(p|div|table|ul|ol|li|h[1-6]|blockquote|pre)', stripped, re.I):
            wrapped.append(stripped)
        else:
            wrapped.append(f'<p>{stripped}</p>')
    return '\n'.join(wrapped)


def preprocess_html(html):
    if not html:
        return ''
    # Check before any transformations add <p> tags
    has_p_tags = bool(re.search(r'<p[\s>]', html, re.I))
    # Strip Gutenberg block comments
    html = re.sub(r'<!-- /?wp:[^\n]*?-->', '', html)
    # Clean up Picasa embeds
    html = replace_picasa_tables(html)
    # Fix paragraph structure for old MT-style posts (bare newlines as separators)
    if not has_p_tags:
        html = wrap_bare_paragraphs(html)
    return html.strip()


def rewrite_fivewells_links(text, slug_map):
    """Rewrite internal youknowjack.fivewells.com links to /blog/ paths."""
    # Pattern: youknowjack.fivewells.com/archives/YYYY/MM/slug.html
    pattern = re.compile(
        r'https?://youknowjack\.fivewells\.com/archives/\d{4}/\d{2}/([^/\s"\')\]]+?)\.html'
    )
    def _replace(m):
        old_slug = m.group(1)
        new_slug = slug_map.get(old_slug, old_slug)
        return f'/blog/{new_slug}/'
    return pattern.sub(_replace, text)


# ── First pass: collect all posts to build a slug map ──────────────────────

tree = ET.parse(sys.argv[1])
channel = tree.getroot().find('channel')
items = list(channel.findall('item'))

# Build mapping: original MT slug (wp:post_name) → new file slug
slug_map = {}     # mt_slug → new_slug
all_posts = []    # list of dicts for second pass

slugs_seen = set()
count = 0

for item in items:
    pt = item.find('wp:post_type', NS)
    status = item.find('wp:status', NS)
    if pt is None or pt.text != 'post':
        continue
    if status is None or status.text != 'publish':
        continue

    title_el = item.find('title')
    title = (title_el.text or '').strip() if title_el is not None else 'Untitled'

    date_el = item.find('wp:post_date', NS)
    date_str = (date_el.text or '').strip() if date_el is not None else ''
    iso_date = date_str[:10] if date_str else '1970-01-01'
    year = iso_date[:4]
    month = iso_date[5:7]

    slug_el = item.find('wp:post_name', NS)
    mt_slug = (slug_el.text or '').strip() if slug_el is not None else ''

    new_slug = slugify(mt_slug) or slugify(title) or f'post-{count}'
    base_slug = new_slug
    n = 2
    while new_slug in slugs_seen:
        new_slug = f'{base_slug}-{n}'
        n += 1
    slugs_seen.add(new_slug)

    if mt_slug:
        slug_map[mt_slug] = new_slug

    html_el = item.find('content:encoded', NS)
    raw_html = (html_el.text or '') if html_el is not None else ''

    cats = []
    for cat_el in item.findall('category'):
        domain = cat_el.get('domain', '')
        if domain == 'category' and cat_el.text and \
                cat_el.text.lower() != 'uncategorized':
            cats.append(cat_el.text.strip())

    # Reconstruct fivewells URL
    fivewells_url = (
        f'{FIVEWELLS_BASE}/{year}/{month}/{mt_slug}.html'
        if mt_slug else ''
    )

    all_posts.append({
        'title': title,
        'iso_date': iso_date,
        'new_slug': new_slug,
        'mt_slug': mt_slug,
        'raw_html': raw_html,
        'cats': cats,
        'fivewells_url': fivewells_url,
    })
    count += 1


# ── Second pass: convert and write ────────────────────────────────────────

out_dir = os.path.join(os.path.dirname(__file__), 'src', 'blog')
os.makedirs(out_dir, exist_ok=True)

for i, post in enumerate(all_posts, 1):
    clean_html = preprocess_html(post['raw_html'])
    md_content = md(clean_html, heading_style='ATX', bullets='-') if clean_html else ''
    # Collapse excess blank lines
    md_content = re.sub(r'\n{3,}', '\n\n', md_content).strip()
    # Rewrite internal fivewells links to /blog/ paths
    md_content = rewrite_fivewells_links(md_content, slug_map)

    title_yaml = yaml_str(post['title'])
    fivewells_yaml = (f'\noriginal_url: {yaml_str(post["fivewells_url"])}'
                      if post['fivewells_url'] else '')

    cats = post['cats']
    cats_yaml = ('\ncategories:\n' + '\n'.join(f'  - {yaml_str(c)}' for c in cats)) if cats else ''

    frontmatter = (
        f'---\n'
        f'title: {title_yaml}\n'
        f'date: {post["iso_date"]}\n'
        f'layout: post.njk'
        f'{fivewells_yaml}'
        f'{cats_yaml}\n'
        f'---\n\n'
    )

    out_path = os.path.join(out_dir, f'{post["new_slug"]}.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter + md_content + '\n')

    print(f'[{i:3d}] {post["iso_date"]}  {post["new_slug"]}.md')

print(f'\nDone: {len(all_posts)} posts written to {out_dir}')
print(f'Slug map has {len(slug_map)} entries')
