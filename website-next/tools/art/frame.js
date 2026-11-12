var q=new URLSearchParams(location.search),f=document.getElementById("f");
if(q.get("nojs"))f.setAttribute("sandbox","allow-same-origin");
f.width=q.get("w")||390;f.height=q.get("h")||844;f.src=q.get("src")||"/";
if(q.get("y"))f.style.marginTop=-q.get("y")+"px";
