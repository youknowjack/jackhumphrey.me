#!/usr/bin/env node
// Migrates a WordPress WXR export to Eleventy markdown posts.
// Usage: node migrate-wp.js <path-to-export.xml>

const fs = require('fs');
const path = require('path');
const { parseString } = require('xml2js');
const TurndownService = require('turndown');

const xmlPath = process.argv[2];
if (!xmlPath) {
  console.error('Usage: node migrate-wp.js <export.xml>');
  process.exit(1);
}

const td = new TurndownService({
  headingStyle: 'atx',
  bulletListMarker: '-',
  codeBlockStyle: 'fenced',
});

// Strip Gutenberg block comments before converting
function cleanWpHtml(html) {
  if (!html) return '';
  return html
    .replace(/<!-- wp:[^\n]*?-->/g, '')
    .replace(/<!-- \/wp:[^\n]*?-->/g, '')
    .trim();
}

function slugify(s) {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function sanitizeYaml(s) {
  if (!s) return '';
  // Escape any existing quotes and wrap in double quotes if needed
  if (s.includes('"') || s.includes("'") || s.includes(':') || s.includes('#') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '\\"') + '"';
  }
  return s;
}

const xml = fs.readFileSync(xmlPath, 'utf8');

parseString(xml, { explicitArray: true }, (err, result) => {
  if (err) { console.error('XML parse error:', err); process.exit(1); }

  const channel = result.rss.channel[0];
  const items = channel.item || [];

  const outDir = path.join(__dirname, 'src', 'blog');
  fs.mkdirSync(outDir, { recursive: true });

  let count = 0;
  const slugsSeen = new Set();

  for (const item of items) {
    const postType = item['wp:post_type']?.[0];
    const status = item['wp:status']?.[0];

    if (postType !== 'post' || status !== 'publish') continue;

    const title = item.title?.[0] || 'Untitled';
    const dateStr = item['wp:post_date']?.[0] || '';
    const rawSlug = item['wp:post_name']?.[0] || slugify(title);

    // Ensure unique, clean slug
    let slug = slugify(rawSlug) || slugify(title) || `post-${count}`;
    if (slugsSeen.has(slug)) slug = slug + '-' + (++count);
    slugsSeen.add(slug);

    const htmlContent = item['content:encoded']?.[0] || '';
    const cleanHtml = cleanWpHtml(htmlContent);
    const mdContent = cleanHtml ? td.turndown(cleanHtml) : '';

    // Categories (exclude 'Uncategorized')
    const cats = (item.category || [])
      .filter(c => typeof c === 'object' ? c.$.domain === 'category' : true)
      .map(c => typeof c === 'object' ? c._ : c)
      .filter(c => c && c.toLowerCase() !== 'uncategorized');

    // Date: parse to ISO
    const date = dateStr ? dateStr.replace(' ', 'T') + 'Z' : new Date().toISOString();
    const isoDate = dateStr.slice(0, 10); // YYYY-MM-DD

    const titleYaml = sanitizeYaml(title);
    const catsYaml = cats.length
      ? `\ncategories:\n${cats.map(c => `  - ${sanitizeYaml(c)}`).join('\n')}`
      : '';

    const frontmatter = `---
title: ${titleYaml}
date: ${isoDate}
layout: post.njk${catsYaml}
---

`;

    const outPath = path.join(outDir, `${slug}.md`);
    fs.writeFileSync(outPath, frontmatter + mdContent, 'utf8');
    count++;
    console.log(`[${count}] ${isoDate} ${slug}.md`);
  }

  console.log(`\nDone: ${count} posts written to ${outDir}`);
});
