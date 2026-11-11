const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const chatWindow = document.getElementById('chat-window');
function addMessage(text, sender, meta) {
  const msg=document.createElement('div'); msg.className='msg '+sender;
  const bubble=document.createElement('div'); bubble.className='bubble'; bubble.textContent=text; msg.appendChild(bubble);
  if(meta){const el=document.createElement('div');el.className='bubble meta';el.textContent=meta;msg.appendChild(el);}
  chatWindow.appendChild(msg); chatWindow.scrollTop=chatWindow.scrollHeight;
}
form.addEventListener('submit',async e=>{
 e.preventDefault(); const text=input.value.trim(); if(!text)return;
 addMessage(text,'user');input.value='';
 try{
  const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
  const data=await res.json();
  if(data.blocked){addMessage(data.response,'bot','Blocked and reported to HR');return;}
  if(!res.ok||data.error){addMessage(data.error||'Sorry, something went wrong.','bot');return;}
  const meta=`Topic: ${data.intent} · match: ${data.confidence}`+(data.escalated?' · sent to HR for review':'');
  addMessage(data.response,'bot',meta);
 }catch(err){addMessage('Network error — please try again.','bot');}
});
