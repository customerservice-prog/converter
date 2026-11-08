"use strict";
const site=document.getElementById("site"), error=document.getElementById("error");
chrome.storage.local.get(["baseUrl"],x=>site.value=x.baseUrl||"");
site.addEventListener("change",()=>chrome.storage.local.set({baseUrl:site.value.trim().replace(/\/+$/,"")}));
function convert(format){
  const base=site.value.trim().replace(/\/+$/,"");
  let location;
  try{
    location=new URL(base);
    if(location.protocol!=="https:"&&!(location.protocol==="http:"&&location.hostname==="localhost"))
      throw Error("Use your deployed HTTPS site address.");
  }catch{error.textContent="Enter a valid deployed HTTPS site URL first.";return;}
  chrome.storage.local.set({baseUrl:base});
  chrome.tabs.query({active:true,currentWindow:true},tabs=>{
    const tab=tabs[0];let parsed;
    try{parsed=new URL(tab.url);}catch{error.textContent="Open a YouTube video page first.";return;}
    const host=parsed.hostname.toLowerCase();
    if(!["youtube.com","www.youtube.com","youtu.be","www.youtu.be","m.youtube.com","music.youtube.com"].includes(host)){
      error.textContent="This shortcut works on YouTube video pages.";return;
    }
    chrome.tabs.create({url:base+"/?format="+format+"&url="+encodeURIComponent(tab.url)});
    window.close();
  });
}
document.getElementById("mp3").addEventListener("click",()=>convert("mp3"));
document.getElementById("mp4").addEventListener("click",()=>convert("mp4"));
