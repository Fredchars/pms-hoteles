const S=[...document.querySelectorAll('.slide')];let i=0;
function fit(){const st=document.getElementById('stage');if(window.matchMedia('(max-width:900px)').matches){st.style.transform='none';return}
 const k=Math.min(innerWidth/1280,innerHeight/720);st.style.transform='scale('+k+')'}
function go(n){i=Math.max(0,Math.min(S.length-1,n));S.forEach((s,j)=>s.classList.toggle('on',j===i));
 document.getElementById('cnt').textContent=(i+1)+' / '+S.length;document.getElementById('bar').style.width=((i+1)/S.length*100)+'%';
 history.replaceState(null,'','#'+(i+1))}
addEventListener('keydown',e=>{if(['ArrowRight','ArrowDown','PageDown',' '].includes(e.key)){e.preventDefault();go(i+1)}
 if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();go(i-1)}if(e.key==='Home')go(0);if(e.key==='End')go(S.length-1)});
let x0=null;addEventListener('touchstart',e=>x0=e.touches[0].clientX);addEventListener('touchend',e=>{if(x0===null)return;const d=e.changedTouches[0].clientX-x0;if(Math.abs(d)>50)go(i+(d<0?1:-1));x0=null});
addEventListener('resize',fit);fit();go((parseInt(location.hash.slice(1))||1)-1);
