/**
 * fetch_news.js — Macro News Fetcher
 * 
 * Sources:
 *   1. GDELT DOC 2.0 API — global macro news filtered by keywords
 *   2. Federal Reserve RSS — FOMC statements, speeches, minutes
 * 
 * Output: data/news/macro_news.json
 * 
 * Usage:
 *   const { fetchAllNews, loadNewsFromDisk } = require('./lib/fetch_news');
 *   await fetchAllNews();                    // fetch + save
 *   const news = loadNewsFromDisk();         // read cached
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const NEWS_DIR = path.join(__dirname, '..', 'data', 'news');
const NEWS_FILE = path.join(NEWS_DIR, 'macro_news.json');

// ── GDELT Config ──────────────────────────────────────────────
// Keep query short — long OR chains cause GDELT to time out
// GDELT requires OR'd terms wrapped in parentheses
const GDELT_QUERIES = [
  '(inflation OR recession OR tariff OR unemployment)',
  '("federal reserve" OR "interest rate" OR "rate cut" OR "central bank")',
];

function buildGdeltUrl(query) {
  return `http://api.gdeltproject.org/api/v2/doc/doc`
    + `?query=${encodeURIComponent(query)}`
    + `&mode=artlist`
    + `&maxrecords=15`
    + `&format=json`
    + `&timespan=24h`
    + `&sourcelang=eng`;
}

// ── Fed RSS Config ────────────────────────────────────────────
const FED_RSS_URL = 'https://www.federalreserve.gov/feeds/press_all.xml';

// ── Helpers ───────────────────────────────────────────────────

function httpGet(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { timeout: timeoutMs }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        // follow redirect
        return httpGet(res.headers.location, timeoutMs).then(resolve).catch(reject);
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function parseGdeltDate(seendate) {
  // GDELT format: "20260901T073000Z"
  if (!seendate || seendate.length < 15) return null;
  try {
    const y = seendate.slice(0, 4);
    const m = seendate.slice(4, 6);
    const d = seendate.slice(6, 8);
    const h = seendate.slice(9, 11);
    const min = seendate.slice(11, 13);
    const s = seendate.slice(13, 15);
    return new Date(`${y}-${m}-${d}T${h}:${min}:${s}Z`).toISOString();
  } catch {
    return null;
  }
}

function parseRssDate(pubDate) {
  try {
    return new Date(pubDate).toISOString();
  } catch {
    return null;
  }
}

// Simple XML tag extractor (no dependency needed for RSS)
function extractTag(xml, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, 'i');
  const m = xml.match(re);
  return m ? m[1].trim().replace(/<!\[CDATA\[|\]\]>/g, '') : null;
}

function extractAllItems(xml) {
  const items = [];
  const re = /<item>([\s\S]*?)<\/item>/gi;
  let m;
  while ((m = re.exec(xml)) !== null) {
    items.push(m[1]);
  }
  return items;
}

// ── GDELT Fetcher ─────────────────────────────────────────────

async function fetchGdelt() {
  const allArticles = [];
  for (let i = 0; i < GDELT_QUERIES.length; i++) {
    const query = GDELT_QUERIES[i];
    // GDELT rate limit: 1 request per 5 seconds
    if (i > 0) await new Promise(r => setTimeout(r, 6000));
    try {
      const url = buildGdeltUrl(query);
      console.log(`[News] GDELT query ${i+1}/${GDELT_QUERIES.length}: ${query.slice(0, 50)}...`);
      const { status, body } = await httpGet(url, 30000);
      if (status === 429) {
        console.log(`[News] GDELT rate limited (429), skipping remaining queries`);
        break;
      }
      if (status !== 200) {
        console.log(`[News] GDELT returned HTTP ${status}`);
        continue;
      }
      if (!body || body.length < 10 || !body.trim().startsWith('{')) {
        console.log(`[News] GDELT returned non-JSON: ${body.slice(0, 80)}`);
        continue;
      }
      const data = JSON.parse(body);
      const articles = data.articles || [];
      console.log(`[News] GDELT got ${articles.length} articles`);
      for (const a of articles) {
        if (a.language && a.language !== 'English') continue;
        allArticles.push({
          title: a.title || '',
          url: a.url || '',
          source: a.domain || '',
          sourceType: 'gdelt',
          date: parseGdeltDate(a.seendate),
          image: a.socialimage || null,
          country: a.sourcecountry || '',
        });
      }
    } catch (err) {
      console.log(`[News] GDELT query failed: ${err.message}`);
    }
  }
  console.log(`[News] GDELT total: ${allArticles.length} English articles`);
  return allArticles.filter(a => a.title && a.url && a.date);
}

// ── Fed RSS Fetcher ───────────────────────────────────────────

async function fetchFedRss() {
  try {
    console.log('[News] Fetching Fed RSS...');
    const { status, body } = await httpGet(FED_RSS_URL);
    if (status !== 200) {
      console.log(`[News] Fed RSS returned HTTP ${status}`);
      return [];
    }
    const items = extractAllItems(body);
    console.log(`[News] Fed RSS returned ${items.length} items`);
    return items.slice(0, 20).map(item => {
      const title = extractTag(item, 'title') || '';
      const url = extractTag(item, 'link') || '';
      const pubDate = extractTag(item, 'pubDate') || extractTag(item, 'dc:date') || '';
      const desc = extractTag(item, 'description') || '';
      return {
        title,
        url,
        source: 'federalreserve.gov',
        sourceType: 'fed',
        date: parseRssDate(pubDate),
        image: null,
        country: 'United States',
        description: desc.slice(0, 200),
      };
    }).filter(a => a.title && a.url && a.date);
  } catch (err) {
    console.log(`[News] Fed RSS fetch failed: ${err.message}`);
    return [];
  }
}

// ── Main ──────────────────────────────────────────────────────

async function fetchAllNews() {
  const [gdelt, fed] = await Promise.all([fetchGdelt(), fetchFedRss()]);

  // Merge, dedupe by URL, sort by date descending
  const seen = new Set();
  const merged = [];
  for (const a of [...fed, ...gdelt]) {
    if (!seen.has(a.url)) {
      seen.add(a.url);
      merged.push(a);
    }
  }
  merged.sort((a, b) => new Date(b.date) - new Date(a.date));

  // Keep top 50
  const result = {
    updated: new Date().toISOString(),
    gdeltCount: gdelt.length,
    fedCount: fed.length,
    articles: merged.slice(0, 50),
  };

  // Save to disk
  if (!fs.existsSync(NEWS_DIR)) fs.mkdirSync(NEWS_DIR, { recursive: true });
  fs.writeFileSync(NEWS_FILE, JSON.stringify(result, null, 2));
  console.log(`[News] Saved ${result.articles.length} articles to macro_news.json`);
  return result;
}

function loadNewsFromDisk() {
  try {
    if (fs.existsSync(NEWS_FILE)) {
      return JSON.parse(fs.readFileSync(NEWS_FILE, 'utf8'));
    }
  } catch (err) {
    console.log(`[News] Failed to load cached news: ${err.message}`);
  }
  return { updated: null, gdeltCount: 0, fedCount: 0, articles: [] };
}

module.exports = { fetchAllNews, loadNewsFromDisk };
