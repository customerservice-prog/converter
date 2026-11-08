"use strict";
const $=id=>document.getElementById(id);
const clean=s=>String(s||"").trim();
const routes={
 "/faq":{
   eyebrow:"GOOD TO KNOW",title:"Frequently asked questions",subtitle:"Everything you need to know about using ClipConvert.",
   html:[
    ["What is ClipConvert?","A web tool that converts permitted public YouTube videos into downloadable MP3 audio or MP4 video using server-side FFmpeg and yt-dlp."],
    ["Is the converter free?","Yes. There is no account, subscription or payment required. To protect the server from overload, a daily usage limit applies."],
    ["What YouTube links work?","Normal watch URLs, youtu.be share links, Shorts, embed URLs, and finished livestream URLs. Private, age-gated or otherwise restricted content may fail."],
    ["Which formats are available?","Best available (Auto) is selected by default. For MP3, Auto encodes the best source audio at up to 320 kbps; this cannot improve a lower-quality source. For MP4, Auto chooses the highest available video resolution without a fixed cap. You can also choose manual quality limits."],
    ["How long can my video be?","Up to 240 minutes for MP3 conversion and up to 30 minutes for MP4 conversion."],
    ["Why does a conversion sometimes fail?","YouTube may restrict access, the original may be unavailable, the source may exceed size limits, or the server may be temporarily busy. Videos that require sign-in or bypassing restrictions are not supported."],
    ["Where is the file saved?","In your browser's normal downloads folder. On phones, check Files or Downloads."],
    ["How long is the download available?","Completed downloads remain temporarily accessible for approximately one hour, after which the server removes them."],
    ["Do you support playlists?","No. Paste a single individual video URL."],
    ["Do I need permission to download?","Yes. Use the service only for media you own or are authorized to download, and observe the platform's terms."]
   ].map(q=>'<article class="info-card"><h3>'+q[0]+'</h3><p>'+q[1]+'</p></article>').join("")
 },
 "/add-on":{
   eyebrow:"BROWSER TOOL",title:"Convert with one click.",subtitle:"A lightweight extension lets you send the video in your current browser tab to ClipConvert.",
   html:'<article class="info-card"><h3>Browser extension</h3><p>Extension source is included in this project under <code>extension/</code>. It works as an unpacked extension in Chrome, Edge and Opera. Firefox also supports a temporary installation for development and testing.</p><ol><li>Download or clone the repository.</li><li>In your Chromium browser, open the Extensions page and enable Developer Mode.</li><li>Choose Load unpacked and select the <code>extension</code> directory.</li><li>Open the extension popup and enter the HTTPS address of your deployed ClipConvert site.</li><li>Open a YouTube video and click MP3 or MP4 in the extension.</li></ol><p>For Firefox, use <code>about:debugging</code>, then load the manifest as a temporary extension. Store listings are not published automatically and require review by each browser store.</p></article><article class="info-card"><h3>No installation preferred?</h3><p>Use our <a href="/bookmarklet">bookmarklets</a> instead.</p></article>'
 },
 "/bookmarklet":{
   eyebrow:"ONE-CLICK SHORTCUTS",title:"Save a click. Or three.",subtitle:"Drag a shortcut into your bookmarks bar and use it from a YouTube video page.",
   html:'<article class="info-card"><h3>Bookmarklets</h3><p>Drag one of these links to your browser bookmarks bar. While viewing a YouTube video, select it to open ClipConvert with the link and format filled in.</p><p><a id="mp3Bookmarklet" class="bookmarklet-link" href="#">♫ YouTube to MP3</a> &nbsp; <a id="mp4Bookmarklet" class="bookmarklet-link" href="#">▣ YouTube to MP4</a></p><p class="muted">On mobile, manually create a bookmark and paste its URL from the field below.</p><div><label class="field-label" for="bookmarkletCode">Bookmark URL</label><div class="url-field"><input id="bookmarkletCode" readonly aria-label="Bookmarklet URL"><button class="paste-button" type="button" id="copyBookmarklet">Copy</button></div></div><p class="notice">A bookmarklet only pre-fills your URL. You must still confirm that you have rights to download that media.</p></article>'
 },
 "/thumbnail":{
   eyebrow:"EXTRA TOOL",title:"YouTube thumbnail downloader",subtitle:"Save the standard thumbnail for a video you have permission to use.",
   html:'<article class="info-card"><form class="simple-form" id="thumbForm"><label>Video URL<input id="thumbUrl" placeholder="https://www.youtube.com/watch?v=…" required></label><button type="submit">Get thumbnail ↗</button></form><p id="thumbError" class="form-error" role="alert" hidden></p><div id="thumbResult" class="thumb-result" hidden><img id="thumbImage" alt="YouTube video thumbnail"><a class="inline-button" id="thumbDownload" href="#">↓ Download JPG</a></div></article>'
 },
 "/contact":{
   eyebrow:"SAY HELLO",title:"Contact us",subtitle:"Questions, error reports or rights concerns? Send us a message.",
   html:'<article class="info-card"><form id="contactForm" class="simple-form"><label>Name<input id="contactName" maxlength="80" required></label><label>Email<input id="contactEmail" type="email" maxlength="254" required></label><label>Message<textarea id="contactMessage" minlength="8" maxlength="3000" placeholder="For a conversion error, include the video link and what went wrong." required></textarea></label><p class="muted">This form sends through the site’s configured mail server. If no mail server is configured, submission will explain that it is unavailable.</p><button type="submit">Send message ↗</button><p id="contactResult" role="status"></p></form></article>'
 },
 "/privacy":{
   eyebrow:"YOUR DATA",title:"Privacy information",subtitle:"A straightforward explanation of how this open-source starter handles information.",
   html:'<article class="info-card"><h3>What the site processes</h3><p>To complete a request, the server processes a YouTube URL, video metadata and a temporary converted file. It also keeps a short-lived conversion job ID and rate-limit counters based on the network address visible to the server.</p><h3>Storage and deletion</h3><p>Conversion files are temporary and removed after the download window (normally one hour). Contact messages, when enabled, are sent by email. Hosting providers may retain access and security logs outside the application.</p><h3>Ads and trackers</h3><p>The provided application code includes no third-party analytics or advertising scripts. Web fonts are requested from Google Fonts; those font requests may be logged by the provider.</p><h3>Important</h3><p>Before public launch, the operator must provide its actual identity, contact information, hosting/processor details, and any legally required privacy disclosures.</p></article>'
 },
 "/copyright":{
   eyebrow:"RIGHTS & OWNERSHIP",title:"Copyright and content rights",subtitle:"Respecting creators, publishers and other rights holders.",
   html:'<article class="info-card"><h3>Permitted use only</h3><p>Only convert and download content you own or have authorization to download. Using this service does not grant a license to copyrighted media. Respect YouTube’s terms and applicable copyright law.</p><h3>Reporting concerns</h3><p>Rights holders can use the <a href="/contact">contact form</a> to report concerns, including the specific URL and a description of their rights. Contact delivery must be configured by the site operator before launch. This template does not appoint a DMCA agent or establish a formal takedown procedure.</p><h3>Restricted content</h3><p>The backend does not attempt to bypass DRM, account logins, private video access or geographical restrictions. The operator should establish an effective complaint and abuse-handling process before opening this service to the public.</p></article>'
 },
 "/terms":{
   eyebrow:"PLEASE READ",title:"Terms of use",subtitle:"Use this utility responsibly, lawfully and with permission.",
   html:'<article class="info-card"><h3>Use of the service</h3><p>This software is offered as a conversion utility for media you are authorized to download. You are responsible for the content you submit and for compliance with applicable laws and third-party platform terms.</p><h3>Availability</h3><p>Conversions may fail because of restrictions, outages, rate limits or other technical issues. Service is not guaranteed and may be limited to protect performance.</p><h3>Abuse</h3><p>Do not use this service for infringement, unlawful distribution, automated mass-downloading or to circumvent technical protections.</p><h3>Operator details</h3><p>These are preliminary informational terms, not a substitute for finalized terms prepared for the actual operating entity and jurisdiction before production launch.</p></article>'
 }
};
function showError(el,message){const node=$(el);node.textContent=message;node.hidden=!message;}
function getId(raw){
  const text=clean(raw);
  if(/^[\w-]{11}$/.test(text))return text;
  try{
    const u=new URL(text);const host=u.hostname.toLowerCase();
    if(!["youtube.com","www.youtube.com","m.youtube.com","music.youtube.com","youtube-nocookie.com","www.youtube-nocookie.com","youtu.be","www.youtu.be"].includes(host))return "";
    const parts=u.pathname.split("/").filter(Boolean);
    let found="";
    if(host==="youtu.be"||host==="www.youtu.be")found=parts.length===1?parts[0]:"";
    else if(parts.length===2&&["shorts","embed","live","v"].includes(parts[0]))found=parts[1];
    else if(parts[0]==="watch")found=u.searchParams.get("v")||"";
    return /^[\w-]{11}$/.test(found)?found:"";
  }catch{return "";}
}
let format="mp3",pollTimer=null,batchTimer=null,sourceType="youtube";
function enteredBatchLinks(){
  return $("batchUrls").value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
}
function updateBatchCount(){
  const entries=enteredBatchLinks();
  const unique=new Set(entries.map(getId).filter(Boolean));
  $("batchCount").textContent=unique.size+" / 10 unique video links"+
    (entries.length!==unique.size?" ("+entries.length+" lines)":"");
}
function setSource(value){
  sourceType=value;
  $("urlSourceArea").hidden=value!=="youtube";
  $("batchSourceArea").hidden=value!=="batch";
  $("uploadSourceArea").hidden=value!=="file";
  $("youtubeHint").hidden=value!=="youtube";
  $("convertButton").querySelector("span").textContent=value==="batch"?"Convert all videos":"Convert now";
  for(const [which,id] of [["youtube","youtubeSourceButton"],["batch","batchSourceButton"],["file","fileSourceButton"]]){
    const active=value===which;
    $(id).classList.toggle("active",active);
    $(id).setAttribute("aria-pressed",String(active));
  }
  showError("formError","");
}
function setFormat(which){
  format=which;
  document.querySelectorAll(".format-option").forEach(b=>{
    const active=b.dataset.format===which;
    b.classList.toggle("selected",active);b.setAttribute("aria-pressed",String(active));
  });
  const choices=which==="mp3"
    ? [[0,"★ Best available (Auto)"],[320,"320 kbps"],[192,"192 kbps"],[128,"128 kbps"]]
    : [[0,"★ Best available (Auto)"],[2160,"2160p / 4K"],[1440,"1440p / 2K"],[1080,"1080p Full HD"],[720,"720p HD"],[360,"360p"]];
  $("quality").innerHTML=choices.map(q=>'<option value="'+q[0]+'">'+q[1]+"</option>").join("");
  $("quality").value="0";
}
async function jsonOrError(res){
  let json={};try{json=await res.json();}catch{}
  if(!res.ok){
    const reason=json.detail;
    throw new Error(typeof reason==="string"?reason:"Request failed ("+res.status+").");
  }
  return json;
}
function updateProgress(data){
  $("jobTitle").textContent=data.title||"Preparing your video…";
  $("jobStatus").textContent=data.message||"Working on it…";
  const displayedQuality=data.actual_quality ||
    (Number(data.quality)===0?"Best available (Auto)":
      String(data.quality)+(data.format==="mp3"?" kbps":"p"));
  $("jobDetail").textContent=(data.format||format).toUpperCase()+" · "+displayedQuality+
    (data.duration?" · "+Math.ceil(data.duration/60)+" min":"");
  if(data.thumbnail){$("jobThumbnail").src=data.thumbnail;$("jobThumbnail").hidden=false;}
  else $("jobThumbnail").hidden=true;
  const pct=Number(data.progress||0);
  $("jobPercent").textContent=pct+"%";$("progressFill").style.width=pct+"%";$("progressTrack").setAttribute("aria-valuenow",String(pct));
  if(data.state==="ready"){
    $("jobPercent").textContent="100%";
    $("downloadButton").href=data.folder_url || data.download_url;
    $("downloadButton").textContent="↓ Download "+data.format.toUpperCase()+" folder (.zip)";
    $("downloadButton").hidden=false;
    $("folderDownload").href=data.download_url;
    $("folderDownload").hidden=!data.download_url;
    $("folderDownload").textContent="↓ Download "+data.format.toUpperCase()+" file only (fastest)";
    $("jobStatus").textContent="Your file is ready!";
  }
  if(data.state==="error"){
    showError("jobError",data.error||"Conversion failed.");
    $("jobStatus").textContent="Unable to convert";
    $("jobTitle").textContent=String(data.error||"").toLowerCase().includes("sign-in verification")
      ?"YouTube access is restricted"
      :"This conversion could not be completed";
    $("uploadFallbackButton").hidden=false;
  }
}
async function poll(id){
  try{
    const data=await jsonOrError(await fetch("/api/jobs/"+encodeURIComponent(id),{cache:"no-store"}));
    updateProgress(data);
    if(data.state==="queued"||data.state==="working")pollTimer=setTimeout(()=>poll(id),1400);
  }catch(e){showError("jobError",e.message);$("jobStatus").textContent="Could not check conversion";}
}

function makeBatchRow(item,index){
  const row=document.createElement("article");
  row.className="batch-result";
  const thumb=document.createElement("img");
  thumb.className="batch-thumb";
  thumb.alt="";
  thumb.loading="lazy";
  if(item.thumbnail)thumb.src=item.thumbnail;
  row.appendChild(thumb);
  const info=document.createElement("div");
  info.className="batch-result-info";
  const title=document.createElement("strong");
  title.textContent=(index+1)+". "+(item.title||"YouTube video");
  info.appendChild(title);
  const description=document.createElement("span");
  description.textContent=item.state==="ready"
    ?"Ready · "+(item.actual_quality||"Best available")
    :item.state==="error"?"Failed · "+(item.error||"Unknown error")
    :item.state==="working"?(item.message||"Converting")+" · "+(item.progress||0)+"%"
    :"Queued — waiting for an available conversion slot";
  description.className=item.state==="error"?"batch-result-error":"";
  info.appendChild(description);
  row.appendChild(info);
  if(item.state==="ready" && item.download_url){
    const link=document.createElement("a");
    link.href=item.folder_url||item.download_url;
    link.textContent="↓ Folder";
    link.className="batch-item-download";
    link.setAttribute("aria-label","Download folder for "+(item.title||"video "+(index+1)));
    row.appendChild(link);
  }
  return row;
}
function updateBatchPanel(data){
  const terminal=["complete","partial","failed"].includes(data.state);
  const items=Array.isArray(data.items)?data.items:[];
  const progress=items.reduce((sum,item)=>sum+(
    item.state==="ready"||item.state==="error"?100:Math.max(0,Number(item.progress)||0)),0);
  const pct=data.total?Math.min(100,Math.round(progress/data.total)):0;
  $("batchProgressFill").style.width=pct+"%";
  $("batchProgressTrack").setAttribute("aria-valuenow",String(pct));
  $("batchStatus").textContent=terminal
    ?(data.failed?"Batch finished — "+data.failed+" failed":"All videos are ready!")
    :"Converting "+data.total+" videos…";
  $("batchSummary").textContent=data.processed+" of "+data.total+" completed · "+
    data.succeeded+" ready · "+data.failed+" failed";
  $("batchRows").replaceChildren(...items.map(makeBatchRow));
  $("batchDownload").href=data.download_url||"#";
  $("batchDownload").hidden=!data.download_url;
  $("batchDownload").textContent="↓ Download "+data.succeeded+" videos in one ZIP";
  $("batchReset").hidden=!terminal;
  if(terminal && data.state==="failed")
    showError("batchError","None of the videos could be converted. See individual errors above.");
  else showError("batchError","");
}
async function pollBatch(id){
  try{
    const data=await jsonOrError(await fetch("/api/batches/"+encodeURIComponent(id),{cache:"no-store"}));
    updateBatchPanel(data);
    if(data.state==="working")batchTimer=setTimeout(()=>pollBatch(id),1500);
  }catch(error){
    showError("batchError",error.message);
    $("batchReset").hidden=false;
  }
}
function resetBatch(){
  if(batchTimer)clearTimeout(batchTimer);
  $("batchPanel").hidden=true;
  $("convertForm").hidden=false;
  $("batchUrls").value="";
  $("rightsCheck").checked=false;
  updateBatchCount();
  showError("batchError","");
  setSource("batch");
  window.scrollTo({top:0,behavior:"smooth"});
  $("batchUrls").focus();
}

async function submitConversion(e){
  e.preventDefault();
  showError("formError","");
  if(!$("rightsCheck").checked){
    showError("formError","Please confirm you have permission to download or convert this media.");
    return;
  }
  if(sourceType==="youtube" && !getId(clean($("videoUrl").value))){
    showError("formError","Enter a valid YouTube video URL (including Shorts and share links).");
    return;
  }
  if(sourceType==="batch"){
    const links=enteredBatchLinks();
    const unique=new Set(links.map(getId));
    if(links.length<2||unique.size<2){
      showError("formError","Paste at least two different YouTube video links, one per line.");return;
    }
    if(links.length>10 || unique.size>10){
      showError("formError","You can convert up to 10 different video links per batch.");return;
    }
    if(links.some(link=>!getId(link))){
      showError("formError","One or more links are invalid. Use YouTube video, Shorts, or share URLs.");return;
    }
  }
  if(sourceType==="file"){
    const file=$("uploadInput").files[0];
    if(!file){showError("formError","Choose an audio or video file to upload.");return;}
    if(file.size>100*1024*1024){
      showError("formError","Files must be 100 MB or smaller.");
      return;
    }
  }
  $("convertButton").disabled=true;
  $("convertButton").querySelector("span").textContent=sourceType==="file"?"Uploading…":"Starting…";
  try{
    let response;
    if(sourceType==="batch"){
      response=await fetch("/api/batches",{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({links:enteredBatchLinks(),format,
          quality:Number($("quality").value),rights_confirmed:true})});
      const data=await jsonOrError(response);
      $("convertForm").hidden=true;
      $("jobPanel").hidden=true;
      $("batchPanel").hidden=false;
      updateBatchPanel(data);
      pollBatch(data.id);
      return;
    }
    if(sourceType==="file"){
      const payload=new FormData();
      payload.append("file",$("uploadInput").files[0]);
      payload.append("format",format);
      payload.append("quality",$("quality").value);
      payload.append("rights_confirmed","true");
      response=await fetch("/api/upload",{method:"POST",body:payload});
    }else{
      response=await fetch("/api/jobs",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({url:clean($("videoUrl").value),format,
          quality:Number($("quality").value),rights_confirmed:true})});
    }
    const data=await jsonOrError(response);
    $("convertForm").hidden=true;
    $("jobPanel").hidden=false;
    $("downloadButton").hidden=true;
    $("folderDownload").hidden=true;
    $("uploadFallbackButton").hidden=true;
    showError("jobError","");
    updateProgress(data);
    poll(data.id);
  }catch(err){showError("formError",err.message);}
  finally{
    $("convertButton").disabled=false;
    $("convertButton").querySelector("span").textContent=sourceType==="batch"?"Convert all videos":"Convert now";
  }
}
function resetConverter(){
  if(pollTimer)clearTimeout(pollTimer);
  $("convertForm").hidden=false;$("jobPanel").hidden=true;
  $("videoUrl").value="";$("uploadInput").value="";$("uploadFileName").textContent="Choose a file from your device";$("rightsCheck").checked=false;
  showError("formError","");window.scrollTo({top:0,behavior:"smooth"});$("videoUrl").focus();
}
function bookmarklet(fmt){
  const destination=window.location.origin+"/?format="+fmt+"&url=";
  return "javascript:(function(){location.href="+JSON.stringify(destination)+"+encodeURIComponent(location.href)})()";
}
function activatePage(path){
  const page=routes[path];if(!page)return;
  $("homepage").hidden=true;$("secondaryPage").hidden=false;
  $("secondaryEyebrow").textContent=page.eyebrow;$("secondaryTitle").textContent=page.title;
  $("secondarySubtitle").textContent=page.subtitle;$("secondaryContent").innerHTML=page.html;
  document.title=page.title+" — ClipConvert";
  if(path==="/bookmarklet"){
    $("mp3Bookmarklet").href=bookmarklet("mp3");
    $("mp4Bookmarklet").href=bookmarklet("mp4");
    $("bookmarkletCode").value=bookmarklet("mp3");
    $("mp3Bookmarklet").addEventListener("click",e=>{if(!e.isTrusted)e.preventDefault();});
    $("copyBookmarklet").addEventListener("click",async()=>{
      try{await navigator.clipboard.writeText($("bookmarkletCode").value);$("copyBookmarklet").textContent="Copied!";}
      catch{$("bookmarkletCode").select();}
    });
    $("mp4Bookmarklet").addEventListener("mouseenter",()=>$("bookmarkletCode").value=bookmarklet("mp4"));
    $("mp3Bookmarklet").addEventListener("mouseenter",()=>$("bookmarkletCode").value=bookmarklet("mp3"));
  }
  if(path==="/thumbnail")$("thumbForm").addEventListener("submit",e=>{
    e.preventDefault();
    const id=getId($("thumbUrl").value);
    if(!id){showError("thumbError","Enter a valid YouTube video URL.");$("thumbResult").hidden=true;return;}
    showError("thumbError","");
    $("thumbImage").src="https://i.ytimg.com/vi/"+id+"/hqdefault.jpg";
    $("thumbDownload").href="/api/thumbnail/"+id;
    $("thumbResult").hidden=false;
  });
  if(path==="/contact")$("contactForm").addEventListener("submit",async e=>{
    e.preventDefault();const status=$("contactResult");status.textContent="Sending…";
    try{
      await jsonOrError(await fetch("/api/contact",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name:clean($("contactName").value),email:clean($("contactEmail").value),message:clean($("contactMessage").value)})}));
      status.textContent="Message sent successfully!";$("contactForm").reset();
    }catch(err){status.textContent=err.message;}
  });
}
document.addEventListener("DOMContentLoaded",()=>{
  $("copyrightYear").textContent=new Date().getFullYear();
  document.querySelectorAll(".format-option").forEach(b=>b.addEventListener("click",()=>setFormat(b.dataset.format)));
  $("convertForm").addEventListener("submit",submitConversion);
  $("youtubeSourceButton").addEventListener("click",()=>setSource("youtube"));
  $("batchSourceButton").addEventListener("click",()=>setSource("batch"));
  $("batchUrls").addEventListener("input",updateBatchCount);
  $("batchReset").addEventListener("click",resetBatch);
  $("batchPasteButton").addEventListener("click",async()=>{
    try{
      const text=await navigator.clipboard.readText();
      $("batchUrls").value=[$("batchUrls").value.trim(),text.trim()].filter(Boolean).join("\n");
      updateBatchCount();
      $("batchUrls").focus();
    }catch{showError("formError","Clipboard access is unavailable. Paste multiple links manually.");}
  });
  $("fileSourceButton").addEventListener("click",()=>setSource("file"));
  $("uploadInput").addEventListener("change",()=>{
    const file=$("uploadInput").files[0];
    $("uploadFileName").textContent=file?file.name:"Choose a file from your device";
    showError("formError","");
  });
  $("uploadFallbackButton").addEventListener("click",()=>{
    resetConverter();
    setSource("file");
    $("uploadInput").focus();
  });
  $("resetButton").addEventListener("click",resetConverter);
  $("pasteButton").addEventListener("click",async()=>{
    try{$("videoUrl").value=await navigator.clipboard.readText();$("videoUrl").focus();showError("formError","");}
    catch{showError("formError","Clipboard access is unavailable. Paste the link using Ctrl+V or long-press.");}
  });
  $("mobileMenu").addEventListener("click",()=>{
    const isOpen=document.querySelector(".nav").classList.toggle("open");
    $("mobileMenu").setAttribute("aria-expanded",String(isOpen));
  });
  const path=window.location.pathname.replace(/\/$/,"")||"/";
  if(path!=="/"){activatePage(path);$("headerAction").href="/#converter";}
  document.querySelectorAll("[data-nav]").forEach(a=>a.classList.toggle("active",a.getAttribute("href")===path));
  const params=new URLSearchParams(location.search);
  if(params.get("format")==="mp4")setFormat("mp4");
  if(params.has("url"))$("videoUrl").value=params.get("url");
});
