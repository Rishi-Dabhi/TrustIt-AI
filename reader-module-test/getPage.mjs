import puppeteer from 'puppeteer';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

const DEFAULT_URL = 'https://example.com/news-story';
const FLATTEN = false;

let browser

export async function launchBrowser(params) {
  console.log('import.meta.url', import.meta.url);
  console.log('process.argv[1]',process.argv[1]);
  
  
  try {
    browser = await puppeteer.launch(params);
  } catch (err) {
    if (err.message.includes('No usable sandbox')) {
      console.log("You're missing a setup step. Check README.md and setup a sandbox, eg with \n export CHROME_DEVEL_SANDBOX=/opt/google/chrome/chrome-sandbox");
      process.exit(1);      
    }
    else throw(err);
  }
  return browser;
}

export async function closeBrowser() {
  if (browser) {
      await browser.close();
      browserInstance = null;
  }
}

export async function extractArticle(url, logOutput= true ) {
  const browser = await launchBrowser();
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

    if (logOutput) {
      console.log('Headline:', article.title);
      console.log('Content:', content);
    }
    return article.textContent
  } finally {
      await page.close();
  }
}

async function main() {
  const url = process.argv[2] || DEFAULT_URL;
  try {
    await extractArticle(url, false)
    .then(()=> { console.log('Test article: success'); });
  } catch (err) {
    throw(err);
  }
}

main().catch(console.error);
