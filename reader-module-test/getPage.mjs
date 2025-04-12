import puppeteer from 'puppeteer';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

const DEFAULT_URL = 'https://example.com/news-story';
const FLATTEN = false;
const DEFAULT_LOG_CONTENT = false;
const LOG_TIMING = true;
const cacheTtl = 3*60*60*1000;

let browser
let cache = {};

const ignoreList = [
  "",
  "chrome://newtab/",
];
ignoreList.forEach(urlToIgnore => {
  cache[urlToIgnore] = { expires: Infinity };
})

function shouldIgnore(url) {
  if (cache[url]) {
    if (Date.now() < cache[url].expires) {
      console.log(`Ignoring ${url}, which is in cache`);  
      if (Date.now()+cacheTtl > cache[url].expires){
        cache[url].expires = Date.now()+cacheTtl;
        console.log(`Extending ${url} cache TTL`);
      }    
      return true;
    }
    console.log(`Readding ${url} to cache`);
    cache[url].expires = Date.now()+cacheTtl;
    return false;
  }
  console.log(`Adding ${url} to cache`);
  cache[url]={ expires: Date.now()+cacheTtl };
  return false;
}


export async function launchBrowser(params) {
  // console.log('import.meta.url', import.meta.url);
  // console.log('process.argv[1]',process.argv[1]);  
  
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
      browser = null;
  }
}

export async function extractArticle(url, logOutput= DEFAULT_LOG_CONTENT ) {
  const calledAt = Date.now()
  if (LOG_TIMING)
    console.log('      Called extractArticle', Date.now()-calledAt, '    ', url);
  
  browser = browser || await launchBrowser();
  if (LOG_TIMING)
    console.log('                Got browser ', Date.now()-calledAt, '    ', url);

  // Only do work if not recent in cache / ignorelist
  if (!shouldIgnore(url)) {
    const page = await browser.newPage();
    if (LOG_TIMING)
      console.log('Instantiated Puppeteer page ', Date.now()-calledAt, '    ', url);
    try {
      await page.goto(url);
      if (LOG_TIMING)
        console.log('               Fetched page', Date.now()-calledAt, '    ', url);
      const html = await page.content();
      if (LOG_TIMING)
        console.log('                Got content', Date.now()-calledAt, '    ', url);
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
      return { content : article.textContent };  
    } finally {
        await page.close();
    }
  } else {
    return { ignored: 'cache' };
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
