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
    ["How long can my video be?","Up to 240 minutes for MP3 conversion and up to 240 minutes for MP4 conversion."],
    ["Why does a conversion sometimes fail?","YouTube may restrict access, the original may be unavailable, the source may exceed size limits, or the server may be temporarily busy. Videos that require sign-in or bypassing restrictions are not supported."],
    ["Where is the file saved?","In your browser's normal downloads folder. On phones, check Files or Downloads."],
    ["How long is the download available?","Completed downloads remain temporarily accessible for approximately one hour, after which the server removes them."],
    ["Can I convert multiple videos at once?","Yes. Select Multiple links, paste 2–10 different YouTube video URLs (one per line), then choose MP3 or MP4. The app converts up to two concurrently at the best available quality and offers one ZIP with a separate folder for every successfully converted video. Playlists are not supported."],
    ["Do you support YouTube playlists?","No. Paste individual video or Shorts URLs in the Multiple links tab instead."],
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
   html:'<article class="info-card"><form id="contactForm" class="simple-form"><label>Name<input id="contactName" maxlength="80" required></label><label>Email<input id="contactEmail" type="email" maxlength="254" required></label><label>Message<textarea id="contactMessage" minlength="8" maxlength="3000" placeholder="For a conversion error, include the video link and what went wrong." required></textarea></label><p class="muted">Your message is saved in the ClipConvert private support inbox and given a reference number. Notifications are forwarded to email only when a dedicated verified sender is configured. For content rights concerns, use the <a href="/copyright">copyright report form</a>.</p><button type="submit">Send message ↗</button><p id="contactResult" role="status"></p></form></article>'
 },
 "/privacy":{
   eyebrow:"YOUR INFORMATION",title:"Privacy & data handling",subtitle:"How ClipConvert handles conversion files, contact reports and browser data.",
   html:"<article class=\"info-card legal-policy\"><p class=\"legal-meta\"><strong>Effective:</strong> November 8, 2026 · <strong>Website:</strong> ClipConvert</p><h3>What this policy covers</h3><p>ClipConvert is a browser-accessible media conversion service. This notice describes the application's current handling of information, not the practices of third-party websites you visit or link to. The independent operator's legal name and mailing information must be published after those details are confirmed.</p><h3>Information we process</h3><p>To perform conversions, the service processes the URLs you submit, video titles and metadata, output format and quality settings, processing records, and temporary converted files. An HTTP-only signed browser-session cookie is used to manage rate limits and lasts up to 30 days. Direct API users without this cookie may be limited using the network address visible to the server. Your browser can store recent job identifiers in localStorage until you clear its history or site data.</p><h3>Contact and rights requests</h3><p>The contact and copyright reporting forms collect your supplied name, email, report and related links. These messages are kept in a private operator inbox for up to 90 days or deleted earlier by an operator. Outgoing email copies, if enabled, are sent only to a configured support recipient. Do not submit passwords, payment details, identity documents or other unnecessary sensitive information.</p><h3>How information is used</h3><p>Information is used to provide conversions, prevent abuse, troubleshoot failures, secure access to the operator dashboard, respond to support and rights reports, and measure aggregate daily conversion success or failure. The application's current source does not include third-party advertising trackers or behavioral analytics scripts.</p><h3>Storage and deletion</h3><p>Converted files and their job records normally expire about one hour after completion, including downloadable ZIPs. A persistent Railway volume helps those files survive a service restart during the available period; it is not a permanent user media library. Daily aggregate counts contain no submitted name or email, while infrastructure access/security logs may be held under the provider's own retention practices.</p><h3>Service providers and third parties</h3><p>Railway hosts the service and temporary media storage; GitHub supports source code and automated deployment/testing. Conversion requires requesting media and metadata from the originating service, including YouTube where applicable. Google Fonts assets may cause a browser request to Google. Such providers apply their own terms and privacy policies.</p><h3>Your choices and requests</h3><p>You may clear conversion history through the homepage and remove cookies using your browser settings. For questions, corrections, or deletion requests relating to a contact report, use <a href=\"/contact\">the ClipConvert support form</a> and supply the reference provided on submission. Applicable rights depend on your location and circumstances. Please do not submit another person's private data without authorization.</p><h3>Security and changes</h3><p>ClipConvert uses HTTPS, access controls for its private dashboard, temporary media retention, and limits on requests and storage. No system can guarantee absolute security. This page may be updated as providers, domains, or data practices change; substantive updates should be reflected here.</p></article>"
 },
 "/copyright":{
   eyebrow:"RIGHTS & OWNERSHIP",title:"Copyright & rights reporting",subtitle:"An organized way for rights holders to submit detailed reports.",
   html:"<article class=\"info-card legal-policy\"><p class=\"legal-meta\"><strong>Updated:</strong> November 8, 2026</p><h3>Authorized media only</h3><p>ClipConvert is an independent converter, not affiliated with or endorsed by YouTube. Using the service does not transfer copyright ownership or grant permission to download or distribute another party's work. Users must have the rights and follow applicable law and third-party platform terms. The service does not intentionally bypass DRM, private-account requirements or account sign-in restrictions.</p><h3>Reporting copyrighted material</h3><p>If you believe specific content accessible through ClipConvert infringes your rights, submit a detailed notice using the form below. Include the copyrighted work, the material and a URL that identifies it, your contact details, an explanation, a good-faith statement, an accuracy/authority statement, and an electronic signature. The application saves your submission privately for operator review and provides a reference number. The service does not promise removal of material hosted on other websites; where appropriate, the operator may disable its own temporary copies or access.</p><h3>Important distinction regarding DMCA agents</h3><p>This form is a voluntary reporting channel. It is <strong>not</strong> a representation that a designated copyright agent has been registered with the U.S. Copyright Office or that the service automatically qualifies for any DMCA safe harbor. A formal agent registration and public legal contact details must be completed separately if applicable. The operator should handle valid notices promptly and seek qualified legal guidance for disputed claims.</p></article><article class=\"info-card\"><h3>Submit a rights report</h3><form class=\"simple-form\" id=\"copyrightForm\"><label>Your full name or authorized representative<input id=\"rightsName\" maxlength=\"120\" autocomplete=\"name\" required></label><label>Email for a reply<input id=\"rightsEmail\" type=\"email\" maxlength=\"254\" autocomplete=\"email\" required></label><label>Describe the copyrighted work<textarea id=\"rightsWork\" minlength=\"8\" maxlength=\"1200\" required></textarea></label><label>URL identifying the material<input id=\"rightsUrl\" type=\"url\" maxlength=\"2048\" placeholder=\"https://...\" required></label><label>Explain the concern and where the material appears<textarea id=\"rightsDetails\" minlength=\"8\" maxlength=\"3000\" required></textarea></label><label>Electronic signature (typed full name)<input id=\"rightsSignature\" maxlength=\"120\" required></label><label class=\"rights-confirm\"><input type=\"checkbox\" id=\"rightsGoodFaith\" required> I believe in good faith that the reported use is not authorized by the rights owner, its agent or applicable law.</label><label class=\"rights-confirm\"><input type=\"checkbox\" id=\"rightsAccuracy\" required> The information is accurate and I affirm, under penalty of perjury, that I own or am authorized to act for the exclusive right described above.</label><button type=\"submit\" id=\"copyrightSubmit\">Submit copyright report</button><p id=\"copyrightResult\" role=\"status\"></p></form></article>"
 },
 "/terms":{
   eyebrow:"PLEASE READ",title:"Terms of use",subtitle:"Plain-language terms describing what ClipConvert does and its limits.",
   html:"<article class=\"info-card legal-policy\"><p class=\"legal-meta\"><strong>Effective:</strong> November 8, 2026</p><h3>Purpose and eligibility</h3><p>ClipConvert provides a free web interface for converting media that you own or are authorized to download and process. By using the service, you agree to comply with applicable laws, copyright requirements, and the terms of any source platform. Do not use this utility where downloading the material would be unauthorized.</p><h3>What is and is not provided</h3><p>The service offers MP3 and MP4 conversion, uploads of supported media formats, and optional multiple-link processing. Features, output quality, available formats and performance may vary with source media, server capacity and access restrictions. A displayed output bitrate cannot increase quality beyond its source. ClipConvert is not associated with YouTube.</p><h3>Current operational limits</h3><p>To protect stability, the service currently permits up to 100 distinct links in a batch and generally imposes a 120-conversion rolling daily limit for an anonymous browser or network client. Typical upload size is limited to 100 MB, converted files to 512 MB, and source durations to 240 minutes for MP3 or MP4. Limits may change, and completed temporary downloads generally expire about one hour later. Restart-safe temporary storage is not a permanent backup service.</p><h3>Prohibited use</h3><p>You must not submit media that you lack rights to use, infringe intellectual-property rights, bypass technical access protections, abuse automated conversions, probe or attack the infrastructure, or use other people's private content without permission. Accounts or requests can be restricted and offending temporary media may be removed to protect the service or respond to valid complaints.</p><h3>Your responsibility</h3><p>You are responsible for validating your rights, reviewing conversion results before relying on them, and retaining your own copies. ClipConvert does not guarantee uninterrupted operation, continuous availability of a specific third-party source, or error-free media output.</p><h3>Service availability and liability</h3><p>The service is made available on an as-available basis. To the extent permitted by applicable law, the operator disclaims implied warranties relating to fitness, uninterrupted operation and availability. Nothing in these terms limits rights or remedies that cannot lawfully be excluded.</p><h3>Copyright and privacy</h3><p>Read the <a href=\"/copyright\">copyright reporting policy</a> and <a href=\"/privacy\">privacy information</a>. Questions and reports can be submitted through the <a href=\"/contact\">contact form</a>.</p><h3>Operator information</h3><p>ClipConvert is currently identified publicly by its product name. Its separate legal operating entity, mailing address, and any jurisdiction-specific mandatory disclosures must be supplied and verified before this page can be treated as final legal terms. No affiliation with other businesses is asserted.</p></article>"
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
let jobPollErrors=0,batchPollErrors=0;
function enteredBatchLinks(){
  return $("batchUrls").value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
}
function updateBatchCount(){
  const entries=enteredBatchLinks();
  const unique=new Set(entries.map(getId).filter(Boolean));
  $("batchCount").textContent=unique.size+" / 100 unique video links"+
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
    const error=new Error(typeof reason==="string"?reason:"Request failed ("+res.status+").");
    error.status=res.status;
    throw error;
  }
  return json;
}

const HISTORY_KEY="clipconvert-recent-v1";
let activeJobId=null,activeBatchId=null;
function historyEntries(){
  try{
    const parsed=JSON.parse(localStorage.getItem(HISTORY_KEY)||"[]");
    return Array.isArray(parsed)?parsed.slice(0,35):[];
  }catch{return [];}
}
function rememberConversion(type,id){
  if(!id)return;
  const old=historyEntries().filter(x=>!(x.type===type&&x.id===id));
  old.unshift({type,id,time:Date.now()});
  try{localStorage.setItem(HISTORY_KEY,JSON.stringify(old.slice(0,35)));}catch{}
  refreshHistory();
}
async function openSavedConversion(type,id){
  if(pollTimer)clearTimeout(pollTimer);
  if(batchTimer)clearTimeout(batchTimer);
  $("convertForm").hidden=true;
  if(type==="batch"){
    $("jobPanel").hidden=true;$("batchPanel").hidden=false;
    activeBatchId=id;pollBatch(id);
  }else{
    $("batchPanel").hidden=true;$("jobPanel").hidden=false;
    activeJobId=id;poll(id);
  }
  $("converter").scrollIntoView({behavior:"smooth",block:"center"});
}
async function refreshHistory(){
  const entries=historyEntries();
  $("historySection").hidden=!entries.length;
  if(!entries.length)return;
  const results=await Promise.all(entries.map(async entry=>{
    const path=entry.type==="batch"?"/api/batches/":"/api/jobs/";
    try{
      const r=await fetch(path+encodeURIComponent(entry.id),{cache:"no-store"});
      if(r.status===404)return {...entry,expired:true};
      if(!r.ok)return {...entry,problem:true};
      return {...entry,data:await r.json()};
    }catch{return {...entry,problem:true};}
  }));
  const cards=results.map(entry=>{
    const card=document.createElement("article");card.className="history-card";
    const info=document.createElement("div");info.className="history-info";
    const title=document.createElement("strong");
    const sub=document.createElement("span");
    const d=entry.data;
    title.textContent=d?.title||(entry.type==="batch"?"Batch conversion":"Video conversion");
    sub.textContent=entry.expired?"Download expired":entry.problem?"Temporarily unavailable":
      ((entry.type==="batch"?(d.succeeded+" of "+d.total+" ready"):d.state)+
        " · "+(d.actual_quality||d.format?.toUpperCase()||"")) ;
    info.append(title,sub);card.append(info);
    if(d&&!entry.expired){
      const button=document.createElement("button");button.type="button";
      button.textContent=d.state==="ready"||d.state==="complete"||d.state==="partial"?
         "Open downloads":"View progress";
      button.addEventListener("click",()=>openSavedConversion(entry.type,entry.id));
      card.append(button);
    }
    return card;
  });
  $("historyList").replaceChildren(...cards);
}
async function retrySingle(){
  if(!activeJobId)return;
  $("retryVideoButton").disabled=true;
  try{
    const data=await jsonOrError(await fetch("/api/jobs/"+encodeURIComponent(activeJobId)+"/retry",
      {method:"POST"}));
    $("retryVideoButton").hidden=true;showError("jobError","");
    updateProgress(data);poll(activeJobId);
  }catch(err){showError("jobError",err.message)}
  finally{$("retryVideoButton").disabled=false;}
}
async function retryBatch(){
  if(!activeBatchId)return;
  $("batchRetry").disabled=true;
  try{
    const data=await jsonOrError(await fetch("/api/batches/"+encodeURIComponent(activeBatchId)+"/retry",
      {method:"POST"}));
    $("batchRetry").hidden=true;showError("batchError","");
    updateBatchPanel(data);pollBatch(activeBatchId);
  }catch(err){showError("batchError",err.message);}
  finally{$("batchRetry").disabled=false;}
}

function updateProgress(data){
  $("jobTitle").textContent=data.title||"Preparing your video…";
  $("jobStatus").textContent=data.state==="queued" && data.queue_position
    ? "Waiting in queue · position "+data.queue_position
    : (data.message||"Working on it…");
  $("retryVideoButton").hidden=!data.retry_url;
  const displayedQuality=data.actual_quality ||
    (Number(data.quality)===0?"Best available (Auto)":
      String(data.quality)+(data.format==="mp3"?" kbps":"p"));
  $("jobDetail").textContent=(data.format||format).toUpperCase()+" · "+displayedQuality+
    (data.duration?" · "+Math.ceil(data.duration/60)+" min":"")+
    (data.state==="ready" && data.format==="mp4" && data.audio_codec==="aac"
      ?" · AAC audio verified":"");
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
    jobPollErrors=0;
    if(data.state!=="error")showError("jobError","");
    updateProgress(data);
    if(data.state==="queued"||data.state==="working")pollTimer=setTimeout(()=>poll(id),1400);
  }catch(e){
    if(e.status===404){
      showError("jobError","This conversion has expired. Please start another.");
      $("jobStatus").textContent="Download expired";
      return;
    }
    jobPollErrors++;
    if(jobPollErrors<=20){
      $("jobStatus").textContent="Reconnecting to the converter…";
      showError("jobError","A brief connection interruption occurred. Your saved conversion will resume when the server is reachable.");
      pollTimer=setTimeout(()=>poll(id),Math.min(12000,2000+jobPollErrors*750));
    }else{
      showError("jobError","The server is unavailable. Your conversion was saved; refresh this page to check again.");
    }
  }
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
  description.textContent=item.state==="downloaded"?"Downloaded · server copy deleted"
    :item.state==="ready"
    ?"Ready · "+(item.actual_quality||"Best available")+(item.audio_codec==="aac"?" · AAC audio verified":"")
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
    ["ready","downloaded","error"].includes(item.state)?100:Math.max(0,Number(item.progress)||0)),0);
  const pct=data.total?Math.min(100,Math.round(progress/data.total)):0;
  $("batchProgressFill").style.width=pct+"%";
  $("batchProgressTrack").setAttribute("aria-valuenow",String(pct));
  const hadStorageFailures=/storage (is )?full|storage full/i.test(data.message||"") ||
    items.some(item=>item.state==="error"&&/storage (is )?full|not enough storage/i.test(item.error||""));
  const storageBlocked=Number(data.storage_free_mb??99999)<200;
  $("batchStatus").textContent=storageBlocked
    ? "Storage full — "+(data.available??data.succeeded)+" videos available for download"
    : terminal
      ? (data.failed?"Batch finished — "+data.failed+" failed":"All videos are ready!")
      : "Converting "+data.total+" videos…";
  $("batchSummary").textContent=data.processed+" of "+data.total+" completed · "+
    (data.available??data.succeeded)+" ready · "+(data.succeeded-(data.available??data.succeeded))+" downloaded · "+data.failed+" failed";
  $("batchRows").replaceChildren(...items.map(makeBatchRow));
  $("batchDownload").href=data.download_url||"#";
  $("batchDownload").hidden=!data.download_url;
  $("batchDownload").textContent="↓ Download "+(data.available??data.succeeded)+" videos in one ZIP";
  $("batchReset").hidden=!terminal;
  $("batchRetry").hidden=!(terminal && Number(data.failed)>0);
  if(storageBlocked)
    showError("batchError","Storage is low. Download available videos to free server space automatically. Completed transfers are deleted from ClipConvert.");
  else if(hadStorageFailures)
    showError("batchError","Some videos failed when storage was low. Finished downloads are removed from the server automatically; retry failed videos when sufficient space is free.");
  else if(terminal && data.state==="failed")
    showError("batchError","None of the videos could be converted. See individual errors above.");
  else showError("batchError","");
}
async function pollBatch(id){
  try{
    const data=await jsonOrError(await fetch("/api/batches/"+encodeURIComponent(id),{cache:"no-store"}));
    batchPollErrors=0;
    updateBatchPanel(data);
    if(data.state==="working")batchTimer=setTimeout(()=>pollBatch(id),1500);
  }catch(error){
    if(error.status===404){
      showError("batchError","This batch has expired. Start another batch.");
      $("batchReset").hidden=false;
      return;
    }
    batchPollErrors++;
    if(batchPollErrors<=20){
      $("batchStatus").textContent="Checking connection to your saved batch…";
      showError("batchError",error.status>=500
        ?"ClipConvert returned a server error. Retrying the status check; any completed downloads shown above remain available."
        :"Connection interrupted. Retrying the status check without submitting the videos again.");
      batchTimer=setTimeout(()=>pollBatch(id),Math.min(12000,2000+batchPollErrors*750));
    }else{
      showError("batchError","The server is unavailable. Your batch is saved; refresh this page to check its progress.");
      $("batchReset").hidden=false;
    }
  }
}
function resetBatch(){
  if(batchTimer)clearTimeout(batchTimer);
  batchPollErrors=0;
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
    if(links.length>100 || unique.size>100){
      showError("formError","You can convert up to 100 different video links per batch.");return;
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
      activeBatchId=data.id;
      rememberConversion("batch",data.id);
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
    activeJobId=data.id;
    rememberConversion("job",data.id);
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
  jobPollErrors=0;
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
  if(path==="/copyright")$("copyrightForm").addEventListener("submit",async event=>{
    event.preventDefault();
    const output=$("copyrightResult"),submit=$("copyrightSubmit");
    output.textContent="Saving your report…";
    submit.disabled=true;
    try{
      const payload={
        name:clean($("rightsName").value),email:clean($("rightsEmail").value),
        work:clean($("rightsWork").value),material_url:clean($("rightsUrl").value),
        details:clean($("rightsDetails").value),signature:clean($("rightsSignature").value),
        good_faith:$("rightsGoodFaith").checked,accuracy:$("rightsAccuracy").checked
      };
      const answer=await jsonOrError(await fetch("/api/copyright/report",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}));
      output.textContent="Your report is saved for review. Reference "+answer.reference+". Save this number.";
      $("copyrightForm").reset();
    }catch(error){output.textContent=error.message;}
    finally{submit.disabled=false;}
  });
  if(path==="/contact")$("contactForm").addEventListener("submit",async e=>{
    e.preventDefault();const status=$("contactResult");status.textContent="Sending…";
    try{
      const answer=await jsonOrError(await fetch("/api/contact",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name:clean($("contactName").value),email:clean($("contactEmail").value),message:clean($("contactMessage").value)})}));
      status.textContent="Message saved successfully. Reference "+(answer.reference||"")+".";
      $("contactForm").reset();
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
  $("batchRetry").addEventListener("click",retryBatch);
  $("retryVideoButton").addEventListener("click",retrySingle);
  $("historyClear").addEventListener("click",()=>{
    try{localStorage.removeItem(HISTORY_KEY)}catch{}
    $("historySection").hidden=true;$("historyList").replaceChildren();
  });
  refreshHistory();
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
