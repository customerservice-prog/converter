import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const origin = 'https://clipconvert-web-production.up.railway.app';
const browser = await chromium.launch({ headless: true, args:['--no-sandbox'] });
const screens=[{name:'desktop', width:1366,height:900},{name:'mobile',width:390,height:844}];

try {
  for(const viewport of screens){
    const page=await browser.newPage({viewport:{width:viewport.width,height:viewport.height}});
    let response,releaseReady=false;
    for(let attempt=0;attempt<50;attempt++){
      response=await page.goto(origin+'/',{waitUntil:'domcontentloaded',timeout:60000});
      if(response?.status()===200){
        const version=await page.locator('link[href*="/assets/site.css"]').getAttribute('href').catch(()=>null);
        if(version?.includes('v=20261108-v5')){releaseReady=true;break;}
      }
      if(attempt%6===0)console.log('Waiting for matching deployed UI release',viewport.name,attempt);
      await page.waitForTimeout(5000);
    }
    assert.equal(releaseReady,true,'The current UI release did not reach production');
    assert.equal(response?.status(),200,viewport.name+' homepage status');
    await page.locator('#converter .converter-card').waitFor({state:'visible'});
    const observed=await page.evaluate(()=>{
      const styles=[...document.querySelectorAll('link[rel="stylesheet"]')]
        .map(el=>new URL(el.href).pathname)
        .filter(path=>path.startsWith('/assets/'));
      const card=document.querySelector('.converter-card');
      return {
        route:document.documentElement.dataset.route,
        styles,
        pageHidden:document.querySelector('#homepage').hidden,
        cardRadius:getComputedStyle(card).borderTopLeftRadius,
        cardBg:getComputedStyle(card).backgroundImage,
        cardWidth:card.getBoundingClientRect().width,
        viewport:window.innerWidth,
        bodyBackground:getComputedStyle(document.body).backgroundImage,
        horizontalOverflow:document.documentElement.scrollWidth>window.innerWidth+2,
        documentWidth:document.documentElement.scrollWidth,
        offscreenElements:[...document.querySelectorAll('body *')].filter(el=>{
          const box=el.getBoundingClientRect();
          return box.width>0 && (box.right>window.innerWidth+2 || box.left< -2)
            && getComputedStyle(el).position!=='absolute';
        }).slice(0,8).map(el=>({tag:el.tagName,className:el.className,rect:el.getBoundingClientRect().toJSON()})),
        firstPaint:performance.getEntriesByType('paint').map(x=>[x.name,Math.round(x.startTime)])
      };
    });
    assert.equal(observed.route,'home');
    assert.deepEqual(observed.styles,['/assets/site.css'],
      viewport.name+': legacy style and premium theme must not load independently');
    assert.equal(observed.pageHidden,false);
    assert.match(observed.cardBg,/gradient/);
    assert.ok(observed.cardRadius==='26px'||observed.cardRadius==='20px',JSON.stringify(observed));
    assert.ok(observed.cardWidth < observed.viewport,JSON.stringify(observed));
    assert.equal(observed.horizontalOverflow,false,JSON.stringify(observed));
    console.log('VISUAL_THEME_OK',viewport.name,JSON.stringify(observed));
    for(const section of ['privacy','faq','copyright']){
      const r=await page.goto(origin+'/'+section,{waitUntil:'domcontentloaded',timeout:60000});
      assert.equal(r?.status(),200,section+' status');
      const secondary=await page.evaluate(()=>({
        route:document.documentElement.dataset.route,
        homeHidden:document.querySelector('#homepage').hidden,
        homeDisplay:getComputedStyle(document.querySelector('#homepage')).display,
        secondaryHidden:document.querySelector('#secondaryPage').hidden,
        heading:document.querySelector('#secondaryTitle').textContent
      }));
      assert.equal(secondary.route,'secondary');
      assert.equal(secondary.homeHidden,true);
      assert.equal(secondary.homeDisplay,'none');
      assert.equal(secondary.secondaryHidden,false);
      assert.ok(secondary.heading.trim(),JSON.stringify(secondary));
      console.log('SECONDARY_NO_HOMEPAGE_FLASH',viewport.name,section);
    }
    await page.close();
  }
  console.log('CLIPCONVERT_FIRST_PAINT_AND_MOBILE_PASSED');
} finally {
  await browser.close();
}
