document.addEventListener('DOMContentLoaded',()=>{
  const slides=[...document.querySelectorAll('[data-slide]')];
  const dots=[...document.querySelectorAll('[data-slide-dot]')];
  let active=0,timer=null,paused=false;
  const show=(n)=>{if(!slides.length)return;active=(n+slides.length)%slides.length;slides.forEach((el,i)=>el.hidden=i!==active);dots.forEach((el,i)=>{el.classList.toggle('active',i===active);el.setAttribute('aria-pressed',i===active?'true':'false')})};
  const start=()=>{if(slides.length>1&&!paused)timer=setInterval(()=>show(active+1),6500)};
  const stop=()=>{if(timer)clearInterval(timer);timer=null};
  dots.forEach((dot,i)=>dot.addEventListener('click',()=>{stop();show(i);start()}));
  document.querySelector('[data-slideshow-toggle]')?.addEventListener('click',(e)=>{paused=!paused;e.currentTarget.setAttribute('aria-pressed',paused?'true':'false');e.currentTarget.textContent=paused?'Play':'Pause';stop();if(!paused)start()});
  show(0);start();
  document.querySelectorAll('[data-show-password]').forEach((button)=>button.addEventListener('click',()=>{const input=document.getElementById(button.dataset.showPassword);if(!input)return;const reveal=input.type==='password';input.type=reveal?'text':'password';button.textContent=reveal?'Hide':'Show';button.setAttribute('aria-pressed',reveal?'true':'false')}));
  document.querySelector('[data-menu-toggle]')?.addEventListener('click',()=>{const nav=document.querySelector('.sidebar');if(!nav)return;const open=nav.classList.toggle('open');document.querySelector('[data-menu-toggle]').setAttribute('aria-expanded',open?'true':'false')});
  document.querySelectorAll('[data-confirm]').forEach((button)=>button.addEventListener('click',(event)=>{if(!window.confirm(button.dataset.confirm))event.preventDefault()}));
});
