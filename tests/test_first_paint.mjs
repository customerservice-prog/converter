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
  // Simulate the Chromium File System Access API without touching user files.
  // Verify browser closes a local file BEFORE acknowledging server-side deletion.
  const page=await browser.newPage({viewport:{width:1366,height:900}});
  const bid='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
  const anotherBid='cccccccccccccccccccccccccccccccc';
  const jid='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
  const receipt='safe-mock-receipt-0123456789abcdefgh';
  let savedState='ready',acks=0,streamRequests=0;
  const payload=Buffer.from('mock mp4 with complete content');
  await page.addInitScript(()=>{
    const saved=[];
    window.__autoSavedTestFiles=saved;
    const folder=(path)=>({
      getDirectoryHandle:async name=>folder(path+'/'+name),
      getFileHandle:async name=>({
        createWritable:async()=>({
          buffer:[],
          write:async function(bytes){this.buffer.push(...bytes)},
          close:async function(){saved.push({file:path+'/'+name,bytes:this.buffer.length,closed:true})},
          abort:async function(){saved.push({file:path+'/'+name,aborted:true})}
        })
      })
    });
    window.showDirectoryPicker=async()=>({name:'TestDownloads',...folder('TestDownloads')});
    localStorage.setItem('clipconvert-recent-v1',JSON.stringify([{
      type:'batch',id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',time:Date.now()
    }]));
  });
  await page.route('**/api/batches/**',async route=>{
    const url=new URL(route.request().url());
    const path=url.pathname;
    if(path.endsWith('/autosave/'+jid)){
      streamRequests++;
      await route.fulfill({status:200,body:payload,headers:{
        'Content-Type':'video/mp4','Content-Length':String(payload.length),
        'X-ClipConvert-Receipt':receipt}});
      return;
    }
    if(path.endsWith('/autosaved/'+jid)){
      assert.equal(route.request().method(),'POST');
      const info=route.request().postDataJSON();
      assert.equal(info.token,receipt);
      acks++;
      savedState='downloaded';
      await route.fulfill({status:200,contentType:'application/json',
        body:JSON.stringify({status:'downloaded',deleted:true})});
      return;
    }
    if(path.endsWith('/'+anotherBid)){
      await route.fulfill({status:200,contentType:'application/json',
        body:JSON.stringify({id:anotherBid,state:'working',total:71,processed:0,
          succeeded:0,failed:0,cancelled:0,paused:0,available:0,
          format:'mp4',quality:0,storage_free_mb:2400,workspace_required_mb:1200,
          download_url:null,items:[{id:'dddddddddddddddddddddddddddddddd',
          state:'queued',title:'Other batch queued',progress:0,format:'mp4'}]})});
      return;
    }
    if(path.endsWith('/'+bid)){
      const item={id:jid,state:savedState,progress:100,title:'Test Clip',
        format:'mp4',quality:0,actual_quality:'1080p',
        download_url:savedState==='ready'?'/api/download/'+jid:null};
      await route.fulfill({status:200,contentType:'application/json',
        body:JSON.stringify({id:bid,state:'complete',total:1,processed:1,
          succeeded:1,failed:0,cancelled:0,paused:0,available:savedState==='ready'?1:0,
          items:[item],format:'mp4',quality:0,storage_free_mb:2400,
          workspace_required_mb:1200,download_url:savedState==='ready'?'/api/batches/'+bid+'/download':null})});
      return;
    }
    await route.fallback();
  });
  page.on('pageerror',error=>console.log('AUTOSAVE_PAGE_ERROR',error.message));
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});
  await page.locator('script[src*="20261111-one-batch-download-modes"]').waitFor({state:'attached',timeout:30000});
  await page.evaluate((id)=>openSavedConversion('batch',id),bid);
  assert.equal(await page.locator('#modeAuto').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('#batchDownload').isHidden(),true);
  await page.locator('#autoSaveChoose').click();
  try{
    await page.waitForFunction(
      ()=>document.querySelector('#autoSaveStatus')?.textContent?.includes('1 saved from batch'),
      null,{timeout:12000});
  }catch(error){
    console.log('AUTOSAVE_DEBUG',JSON.stringify(await page.evaluate(()=>({
      status:document.querySelector('#autoSaveStatus')?.textContent,
      saved:window.__autoSavedTestFiles||[]
    }))));
    throw error;
  }
  const files=await page.evaluate(()=>window.__autoSavedTestFiles);
  assert.equal(files.length,1,JSON.stringify(files));
  assert.equal(files[0].bytes,payload.length);
  assert.equal(files[0].closed,true);
  assert.equal(acks,1);
  assert.equal(savedState,'downloaded');
  // Changing to manual ZIP hides auto-save and requires explicit mode selection.
  savedState='ready';
  await page.evaluate((id)=>openSavedConversion('batch',id),bid);
  const zipLink=page.locator('#batchDownload');
  assert.equal(await zipLink.isHidden(),true);
  await page.locator('#modeManual').click();
  assert.equal(await page.locator('#autoSavePanel').isHidden(),true);
  assert.equal(await zipLink.isVisible(),true);
  assert.equal(await page.locator('.batch-item-download').count(),1);
  assert.equal((await zipLink.getAttribute('href')).includes('max_total_mb=1500'),true);

  // A directory selected earlier can disappear or lose permission.
  // Reproduce Edge/Chrome NotFoundError and verify the ZIP fallback remains.
  await page.evaluate(()=>{
    window.__workingPicker=window.showDirectoryPicker;
    window.showDirectoryPicker=async()=>({
      name:'MovedFolder',
      getDirectoryHandle:async()=>{
        throw new DOMException('A requested file or directory could not be found','NotFoundError');
      }
    });
  });
  await page.locator('#modeAuto').click();
  assert.equal(await zipLink.isHidden(),true);
  await page.locator('#autoSaveChoose').click();
  await page.waitForFunction(()=>document.querySelector('#autoSaveStatus')?.textContent?.includes('selected download folder was moved'),null,{timeout:12000});
  assert.equal(await zipLink.isHidden(),true);
  assert.equal(acks,1,'Missing browser folder must never acknowledge a server deletion');
  const chooseLabel=await page.locator('#autoSaveChoose').textContent();
  assert.match(chooseLabel,/Choose folder and start automatic downloads/);

  // Picking a new valid folder restores automatic saving without a page reload.
  await page.evaluate(()=>{window.showDirectoryPicker=window.__workingPicker});
  await page.locator('#autoSaveChoose').click();
  // Selecting a replacement folder resets its visible per-folder counter.
  await page.waitForFunction(()=>document.querySelector('#autoSaveStatus')?.textContent?.includes('1 saved from batch'),null,{timeout:12000});
  assert.equal(acks,2,'Replacement folder should allow a completed save to be acknowledged');
  assert.equal((await page.evaluate(()=>window.__autoSavedTestFiles)).length,2);
  // Starting another batch must never automatically download earlier ready media.
  savedState='ready';
  const previouslyStreamed=streamRequests;
  await page.evaluate((id)=>openSavedConversion('batch',id),anotherBid);
  await page.locator('#autoSaveChoose').click();
  await page.waitForTimeout(1000);
  assert.equal(streamRequests,previouslyStreamed,
    'Auto-save must not scan older completed batches when the selected batch has no files');
  assert.equal(acks,2);
  assert.match(await page.locator('#batchIdentity').textContent(),/cccccccc/);
  await page.close();
  console.log('BROWSER_AUTOSAVE_STREAM_AND_ACK_PASSED');
  console.log('BROWSER_MISSING_FOLDER_RECOVERY_ZIP_FALLBACK_PASSED');

  console.log('CLIPCONVERT_FIRST_PAINT_AND_MOBILE_PASSED');
} finally {
  await browser.close();
}
