import puppeteer from 'puppeteer';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

const DEFAULT_URL = 'https://example.com/news-story';
const FLATTEN = false;

let browser

export async function launchBrowser(params) {
  browser = await puppeteer.launch(params);
}

export async function closeBrowser() {
  if (browser) {
      await browser.close();
      browserInstance = null;
  }
}

export async function extractArticle(url) {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  try {
    await page.goto(url);
    const html = await page.content();
    const dom = new JSDOM(html);
    const reader = new Readability(dom.window.document);
    const article = reader.parse();

  const content = FLATTEN
      ? article.textContent
      : article.content
        .replace(/<br\s*\/?>/gi, '\n')      // Replace <br> with newlines
        .replace(/<\/p>|<p[^>]*>/gi, '\n')  // Replace <p> tags with newlines
        .replace(/<[^>]+>/g, '')            // Remove all other HTML tags
        .replace(/\n{3,}/g, '\n\n');        // Normalize excessive newlines


    console.log('Headline:', article.title);
    console.log('Content:', content);
    return article.textContent
  } finally {
      await page.close();
  }
}

async function main() {
  const url = process.argv[2] || DEFAULT_URL;
  await extractArticle(url);
}

main().catch(console.error);
