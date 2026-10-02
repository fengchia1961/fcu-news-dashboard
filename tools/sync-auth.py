# -*- coding: utf-8 -*-
"""把各系登入帳密（帳號＝網址代號、密碼＝單位分機）注入 health-check.html 的
「✍️ 改善回饋填寫」分頁。

用法：
    python tools/extract-ext.py     # 1. 分機表 → tools/auth-map.json
    python tools/sync-auth.py       # 2. 注入 health-check.html

⚠ 這是**純前端的防呆門檻，不是真正的資安機制**。html 裡放的是 SHA-256 雜湊
（看原始碼看不到分機號碼），但分機只有 4 位數，懂技術的人在瀏覽器裡暴力試出來
只要幾秒。它擋的是「別系同仁誤改」，不是惡意者。回饋內容本來就存在填表人自己的
瀏覽器 localStorage，登入與否都不影響那份資料。

冪等：可重複執行（資料與版面整段取代、呼叫點有 marker 保護），自動備份。
"""
import hashlib, json, re, shutil, sys, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
HC = HERE.parent / 'health-check.html'
SRC = HERE / 'auth-map.json'

if not SRC.exists():
    sys.exit('找不到 tools/auth-map.json，請先執行：python tools/extract-ext.py')

j = json.loads(SRC.read_text(encoding='utf-8'))
SALT = 'fcu-healthcheck-auth-v1'
sha = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()
h_of = lambda u, p: sha(SALT + '|' + u.strip().lower() + '|' + str(p).strip())

def dept_hash(i, v):
    """auth-overrides.json 若直接給 hash（使用者自行改過密碼），就沿用；否則用分機算。"""
    return v['hash'] if v.get('hash') else h_of(i, v['ext'])


AUTH = {i: dept_hash(i, v) for i, v in j['depts'].items()}
ADMIN_U = j['admin']['user']
ADMIN_H = j['admin'].get('hash') or h_of(ADMIN_U, j['admin']['ext'])

html = HC.read_text(encoding='utf-8')

# ══════════════════════════════════════════════════════════════════
# 1. CSS
# ══════════════════════════════════════════════════════════════════
CSS = '''/* ==AUTH_CSS_START== */
/* ── 改善回饋填寫：登入門檻 ── */
.fb-lock{background:#fff;border:1px solid #e5e4dc;border-left:4px solid #534AB7;border-radius:12px;padding:1.2rem 1.4rem;margin-bottom:.8rem;}
.fb-lock-t{font-size:16px;font-weight:800;color:#1a1a18;display:flex;align-items:center;gap:7px;}
.fb-lock-s{font-size:13px;color:#5F5E5A;line-height:1.85;margin-top:8px;}
.fb-lock-s code{background:#f0efe8;border-radius:4px;padding:1px 6px;font-size:12.5px;}
.fb-lg{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-top:14px;}
.fb-lg-f{display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;}
.fb-lg-f label{font-size:11.5px;font-weight:700;color:#888780;}
.fb-lg-f input{padding:8px 11px;border:1px solid #d3d1c7;border-radius:8px;font-size:14px;font-family:inherit;background:#fff;color:#1a1a18;}
.fb-lg-f input:focus{outline:none;border-color:#534AB7;box-shadow:0 0 0 3px rgba(83,74,183,.12);}
.fb-lg-go{padding:9px 20px;border:none;border-radius:8px;background:#534AB7;color:#fff;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;white-space:nowrap;}
.fb-lg-go:hover{background:#443BA3;}
.fb-lg-err{display:none;margin-top:10px;font-size:13px;font-weight:700;color:#b91c1c;background:#FDECEC;border-radius:7px;padding:7px 11px;}
.fb-who{display:flex;align-items:center;gap:8px;flex-wrap:wrap;background:#EEEDFE;border:1px solid #CFCBF4;border-radius:9px;padding:7px 12px;margin-bottom:.8rem;font-size:12.5px;color:#413a93;}
.fb-who b{font-weight:800;}
.fb-who .adm{background:#534AB7;color:#fff;border-radius:9px;padding:1px 9px;font-size:11px;font-weight:800;}
.fb-who-acts{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap;}
.fb-who-out{background:#fff;border:1px solid #AFA9EC;color:#534AB7;border-radius:7px;padding:3px 11px;font-size:11.5px;font-weight:700;cursor:pointer;font-family:inherit;white-space:nowrap;}
.fb-who-out:hover{background:#E3E1FB;}
/* 變更密碼面板 */
.fb-pw{background:#fff;border:1px solid #e5e4dc;border-left:4px solid #BA7517;border-radius:12px;padding:1rem 1.3rem;margin-bottom:.8rem;}
.fb-pw-t{font-size:14.5px;font-weight:800;color:#1a1a18;display:flex;align-items:center;gap:6px;}
.fb-pw-tgt{font-size:12.5px;color:#5F5E5A;margin-top:9px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.fb-pw-tgt select{padding:5px 9px;border:1px solid #d3d1c7;border-radius:7px;font-size:13px;font-family:inherit;background:#fff;color:#1a1a18;}
.fb-pw-state{font-size:11.5px;color:#888780;}
.fb-pw-note{background:#FDF8EC;border:1px solid #F2DCA8;border-radius:8px;padding:8px 11px;margin-top:10px;font-size:12px;color:#5F5E5A;line-height:1.8;}
.fb-pw-note b{color:#B45309;}
.fb-pw-list{margin-top:12px;border:1px solid #e5e4dc;border-radius:9px;overflow:hidden;}
.fb-pw-list-t{background:#f7f6f1;padding:6px 11px;font-size:11.5px;font-weight:800;color:#5F5E5A;border-bottom:1px solid #e5e4dc;}
.fb-pw-row{display:flex;align-items:center;gap:10px;padding:7px 11px;font-size:12.5px;color:#1a1a18;border-bottom:1px solid #f0efe9;flex-wrap:wrap;}
.fb-pw-row:last-child{border-bottom:none;}
.fb-pw-kind{font-size:11px;font-weight:700;background:#EEEDFE;color:#534AB7;border-radius:9px;padding:2px 9px;white-space:nowrap;}
.fb-pw-at{font-size:11px;color:#B4B2A9;margin-left:auto;white-space:nowrap;}
.fb-pw-x{background:none;border:none;color:#B4B2A9;cursor:pointer;font-size:13px;font-family:inherit;padding:0 4px;}
.fb-pw-x:hover{color:#b91c1c;}
.fb-pw-acts{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px;}
.fb-pw-msg{display:none;margin-top:10px;font-size:12.5px;font-weight:700;color:#b91c1c;background:#FDECEC;border-radius:7px;padding:8px 11px;line-height:1.75;}
.fb-pw-msg.ok{color:#15803d;background:#EDF8F1;}
/* ==AUTH_CSS_END== */
'''
if '==AUTH_CSS_START==' in html:
    html = re.sub(r'/\* ==AUTH_CSS_START==.*?/\* ==AUTH_CSS_END== \*/\n', lambda _m: CSS, html, count=1, flags=re.S)
else:
    anchor = '/* ==FEEDBACK_CSS_START== */'
    assert anchor in html, '找不到 CSS 插入位置（==FEEDBACK_CSS_START==）'
    html = html.replace(anchor, CSS + anchor, 1)

# ══════════════════════════════════════════════════════════════════
# 2. 帳密與登入程式碼
# ══════════════════════════════════════════════════════════════════
CONST = ('const AUTH = ' + json.dumps(AUTH, ensure_ascii=False, separators=(',', ':')) + ';\n'
         + 'const AUTH_ADMIN = ' + json.dumps({'u': ADMIN_U, 'h': ADMIN_H},
                                              ensure_ascii=False, separators=(',', ':')) + ';\n')

JS = '''/* ═══════════════════════════════════════════════════════
   改善回饋填寫分頁：登入門檻  ==AUTH_JS_START==
   帳號＝學系網址代號（如 inde）；密碼＝該單位總機分機（來源：總機分機表）。
   管理者帳號可登入並編輯任何一系。
   html 內只存 SHA-256 雜湊，看原始碼看不到分機；但分機僅 4 位數，
   這是擋「別系同仁誤改」的防呆門檻，不是真正的資安機制。
   更新：python tools/extract-ext.py && python tools/sync-auth.py
═══════════════════════════════════════════════════════ */
const AUTH_SALT = '__SALT__';
__CONST__const AUTH_SS_KEY = 'fcu-healthcheck-auth';

/* 精簡 SHA-256（純 JS，不依賴 crypto.subtle，離線用 file:// 開檔也能運作） */
function fbSha256(str){
  const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
  const rr=(x,n)=>(x>>>n)|(x<<(32-n));
  const bytes=[];
  for(let i=0;i<str.length;i++){
    let c=str.codePointAt(i);
    if(c>0xffff) i++;
    if(c<0x80) bytes.push(c);
    else if(c<0x800) bytes.push(0xc0|(c>>6),0x80|(c&63));
    else if(c<0x10000) bytes.push(0xe0|(c>>12),0x80|((c>>6)&63),0x80|(c&63));
    else bytes.push(0xf0|(c>>18),0x80|((c>>12)&63),0x80|((c>>6)&63),0x80|(c&63));
  }
  const bitLen=bytes.length*8;
  bytes.push(0x80);
  while(bytes.length%64!==56) bytes.push(0);
  const hi=Math.floor(bitLen/4294967296), lo=bitLen>>>0;
  bytes.push((hi>>>24)&255,(hi>>>16)&255,(hi>>>8)&255,hi&255,(lo>>>24)&255,(lo>>>16)&255,(lo>>>8)&255,lo&255);
  const w=new Array(64);
  for(let i=0;i<bytes.length;i+=64){
    for(let t=0;t<16;t++) w[t]=(bytes[i+t*4]<<24)|(bytes[i+t*4+1]<<16)|(bytes[i+t*4+2]<<8)|bytes[i+t*4+3];
    for(let t=16;t<64;t++){
      const s0=rr(w[t-15],7)^rr(w[t-15],18)^(w[t-15]>>>3);
      const s1=rr(w[t-2],17)^rr(w[t-2],19)^(w[t-2]>>>10);
      w[t]=(w[t-16]+s0+w[t-7]+s1)|0;
    }
    let a=H[0],b=H[1],c=H[2],d=H[3],e=H[4],f=H[5],g=H[6],h=H[7];
    for(let t=0;t<64;t++){
      const S1=rr(e,6)^rr(e,11)^rr(e,25);
      const ch=(e&f)^((~e)&g);
      const t1=(h+S1+ch+K[t]+w[t])|0;
      const S0=rr(a,2)^rr(a,13)^rr(a,22);
      const mj=(a&b)^(a&c)^(b&c);
      const t2=(S0+mj)|0;
      h=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;
    }
    H[0]=(H[0]+a)|0;H[1]=(H[1]+b)|0;H[2]=(H[2]+c)|0;H[3]=(H[3]+d)|0;
    H[4]=(H[4]+e)|0;H[5]=(H[5]+f)|0;H[6]=(H[6]+g)|0;H[7]=(H[7]+h)|0;
  }
  return H.map(x=>(x>>>0).toString(16).padStart(8,'0')).join('');
}
function fbAuthHash(u,p){ return fbSha256(AUTH_SALT + '|' + String(u||'').trim().toLowerCase() + '|' + String(p||'').trim()); }

function fbExpected(u){ return u === AUTH_ADMIN.u ? AUTH_ADMIN.h : AUTH[u]; }

/* 登入狀態只存在 sessionStorage：關掉瀏覽器就要重新登入 */
let FB_AUTH = null;
try{ const r = sessionStorage.getItem(AUTH_SS_KEY); if(r) FB_AUTH = JSON.parse(r); }catch(e){}
function fbIsAdmin(){ return !!(FB_AUTH && FB_AUTH.admin); }
function fbCanEdit(id){ return fbIsAdmin() || !!(FB_AUTH && FB_AUTH.u === id); }

function fbLogin(){
  const u = (document.getElementById('fb-lg-u').value || '').trim().toLowerCase();
  const p = (document.getElementById('fb-lg-p').value || '').trim();
  const err = document.getElementById('fb-lg-err');
  const show = m =>{ err.textContent = m; err.style.display = ''; };
  if(!u || !p) return show('請輸入帳號與密碼');
  const known = !!(AUTH[u] || u === AUTH_ADMIN.u);
  if(!known) return show('查無此帳號（帳號為貴系網址代號，如 inde）');
  if(fbAuthHash(u, p) !== fbExpected(u)) return show('密碼不正確');
  FB_AUTH = {u:u, admin: u === AUTH_ADMIN.u};
  try{ sessionStorage.setItem(AUTH_SS_KEY, JSON.stringify(FB_AUTH)); }catch(e){}
  const d = DEPTS.find(x=>x.id===FB_CUR);
  if(d) renderFeedback(d);
}

/* ── 變更密碼 ── */
let FB_PWD_OPEN = false;
function fbPwdToggle(){
  FB_PWD_OPEN = !FB_PWD_OPEN;
  const d = DEPTS.find(x=>x.id===FB_CUR);
  if(d) renderFeedback(d);
}
function fbPwdTarget(){
  const sel = document.getElementById('fb-pw-t');
  return sel ? sel.value : (FB_AUTH ? FB_AUTH.u : '');
}
function fbPwdLabel(u){ return u === AUTH_ADMIN.u ? ('管理者帳號（' + u + '）') : (fbAuthName(u) + '（' + u + '）'); }
function fbPwdMsg(m, ok){
  const el = document.getElementById('fb-pw-msg');
  if(!el) return;
  el.textContent = m;
  el.className = 'fb-pw-msg' + (ok ? ' ok' : '');
  el.style.display = '';
}
/* 待回傳的變更申請（暫存 sessionStorage，純粹是還沒下載的清單） */
const PWD_REQ_KEY = 'fcu-healthcheck-pwdreq';
let FB_PWD_REQ = [];
try{ const r = sessionStorage.getItem(PWD_REQ_KEY); if(r) FB_PWD_REQ = JSON.parse(r) || []; }catch(e){}
function fbPwdReqSave(){ try{ sessionStorage.setItem(PWD_REQ_KEY, JSON.stringify(FB_PWD_REQ)); }catch(e){} }
function fbPwdReqPut(item){
  FB_PWD_REQ = FB_PWD_REQ.filter(x=>x.id !== item.id);
  FB_PWD_REQ.push(item);
  fbPwdReqSave();
}

function fbPwdAdd(){
  const u = fbPwdTarget();
  if(!u) return;
  const needOld = !fbIsAdmin() || u === AUTH_ADMIN.u;
  const oldV = (document.getElementById('fb-pw-o') || {}).value || '';
  const n1 = (document.getElementById('fb-pw-n1').value || '').trim();
  const n2 = (document.getElementById('fb-pw-n2').value || '').trim();
  if(needOld && fbAuthHash(u, oldV.trim()) !== fbExpected(u)) return fbPwdMsg('目前密碼不正確');
  if(n1.length < 4) return fbPwdMsg('新密碼至少 4 個字元');
  if(n1 !== n2) return fbPwdMsg('兩次輸入的新密碼不一致');
  if(fbAuthHash(u, n1) === fbExpected(u)) return fbPwdMsg('新密碼與目前密碼相同');
  fbPwdReqPut({id:u, name:fbPwdLabel(u), hash:fbAuthHash(u, n1), at:new Date().toLocaleString('zh-TW',{hour12:false})});
  fbPwdMsg('已加入變更清單：' + fbPwdLabel(u) + '。請按下方「下載密碼變更檔」回傳公共事務組，重新產製後全校生效；在那之前請繼續用原密碼。', true);
  fbPwdRerender();
}
function fbPwdResetReq(){
  const u = fbPwdTarget();
  if(!u) return;
  const needOld = !fbIsAdmin() || u === AUTH_ADMIN.u;
  const oldV = (document.getElementById('fb-pw-o') || {}).value || '';
  if(needOld && fbAuthHash(u, oldV.trim()) !== fbExpected(u)) return fbPwdMsg('請先在「目前密碼」輸入現在的密碼，才能申請還原');
  fbPwdReqPut({id:u, name:fbPwdLabel(u), reset:true, at:new Date().toLocaleString('zh-TW',{hour12:false})});
  fbPwdMsg('已加入變更清單：把 ' + fbPwdLabel(u) + ' 還原為預設密碼（單位分機）', true);
  fbPwdRerender();
}
function fbPwdDrop(id){
  FB_PWD_REQ = FB_PWD_REQ.filter(x=>x.id !== id);
  fbPwdReqSave();
  fbPwdRerender();
}
function fbPwdRerender(){
  const d = DEPTS.find(x=>x.id===FB_CUR);
  const msg = document.getElementById('fb-pw-msg');
  const keep = msg && msg.style.display !== 'none' ? {t:msg.textContent, ok:msg.className.indexOf('ok')>=0} : null;
  if(d) renderFeedback(d);
  if(keep) fbPwdMsg(keep.t, keep.ok);
}
function fbPwdExport(){
  if(!FB_PWD_REQ.length) return fbPwdMsg('變更清單是空的');
  const payload = {
    format:'fcu-healthcheck-pwd-v1', salt:AUTH_SALT, exported:new Date().toISOString(),
    changes: FB_PWD_REQ.map(x=> x.reset ? {id:x.id, reset:true, changedAt:x.at}
                                        : {id:x.id, hash:x.hash, changedAt:x.at}),
  };
  const tag = FB_PWD_REQ.length === 1 ? FB_PWD_REQ[0].id : 'all';
  fbDownload('密碼變更_' + tag + '_' + fbToday() + '.json', JSON.stringify(payload, null, 1), 'application/json');
  fbPwdMsg('已下載 ' + FB_PWD_REQ.length + ' 筆，請把檔案回傳公共事務組（檔案裡只有雜湊值，沒有密碼原文）。重新產製發布後全校生效。', true);
}

function fbPwdHtml(d){
  if(!FB_PWD_OPEN) return '';
  const admin = fbIsAdmin();
  const cur = admin ? d.id : FB_AUTH.u;
  const opts = admin
    ? `<select id="fb-pw-t">
         <option value="${esc(d.id)}">${esc(fbPwdLabel(d.id))}</option>
         <option value="${esc(AUTH_ADMIN.u)}">${esc(fbPwdLabel(AUTH_ADMIN.u))}</option>
       </select>`
    : `<input id="fb-pw-t" type="hidden" value="${esc(cur)}"><b>${esc(fbPwdLabel(cur))}</b>`;
  const list = FB_PWD_REQ.length ? `<div class="fb-pw-list">
      <div class="fb-pw-list-t">待回傳的變更（${FB_PWD_REQ.length}）</div>
      ${FB_PWD_REQ.map(x=>`<div class="fb-pw-row">
        <span>${esc(x.name || x.id)}</span>
        <span class="fb-pw-kind">${x.reset ? '還原為預設分機密碼' : '設定新密碼'}</span>
        <span class="fb-pw-at">${esc(x.at)}</span>
        <button class="fb-pw-x" onclick="fbPwdDrop('${esc(x.id)}')" title="移除這筆">✕</button>
      </div>`).join('')}
    </div>` : '';
  return `<div class="fb-pw">
    <div class="fb-pw-t"><i class="ti ti-key" style="color:#534AB7;"></i> 變更密碼</div>
    <div class="fb-pw-tgt">變更對象：${opts}</div>
    <div class="fb-pw-note"><i class="ti ti-info-circle"></i>
      密碼由公共事務組統一管理。在這裡設定新密碼後，按「下載密碼變更檔」把檔案回傳公共事務組，
      重新產製發布後<b>全校都改用新密碼</b>；在那之前請繼續使用原密碼。
      檔案裡只有雜湊值，沒有密碼原文，所以<b>請另外告知系上要用的新密碼</b>。
    </div>
    <div class="fb-lg">
      <div class="fb-lg-f"><label>目前密碼${admin ? '<span style="font-weight:400;">（重設他系密碼可留空）</span>' : ''}</label>
        <input id="fb-pw-o" type="password" autocomplete="current-password"></div>
      <div class="fb-lg-f"><label>新密碼（至少 4 字元）</label><input id="fb-pw-n1" type="password" autocomplete="new-password"></div>
      <div class="fb-lg-f"><label>再輸入一次新密碼</label><input id="fb-pw-n2" type="password" autocomplete="new-password"
             onkeydown="if(event.key==='Enter'){event.preventDefault();fbPwdAdd();}"></div>
      <button class="fb-lg-go" onclick="fbPwdAdd()"><i class="ti ti-plus"></i> 加入變更清單</button>
    </div>
    ${list}
    <div class="fb-pw-acts">
      <button class="fb-btn primary" onclick="fbPwdExport()"><i class="ti ti-download"></i> 下載密碼變更檔</button>
      <button class="fb-btn ghost" onclick="fbPwdResetReq()"><i class="ti ti-rotate"></i> 申請還原為預設密碼</button>
      <button class="fb-btn ghost" onclick="fbPwdToggle()"><i class="ti ti-x"></i> 收合</button>
    </div>
    <div class="fb-pw-msg" id="fb-pw-msg" style="display:none;"></div>
  </div>`;
}
function fbLogout(){
  FB_AUTH = null;
  FB_PWD_OPEN = false;
  try{ sessionStorage.removeItem(AUTH_SS_KEY); }catch(e){}
  const d = DEPTS.find(x=>x.id===FB_CUR);
  if(d) renderFeedback(d);
}
function fbAuthName(id){ const d = DEPTS.find(x=>x.id===id); return d ? d.name : id; }

function fbLockHtml(d){
  const wrong = FB_AUTH && !fbIsAdmin() && FB_AUTH.u !== d.id;
  return `<div class="fb-lock">
    <div class="fb-lock-t"><i class="ti ti-lock" style="color:#534AB7;"></i> 請先登入才能填寫${esc(d.name)}的改善回饋</div>
    <div class="fb-lock-s">
      ${wrong ? `目前登入的是 <b>${esc(fbAuthName(FB_AUTH.u))}</b>（<code>${esc(FB_AUTH.u)}</code>），只能填寫該系的回饋。要填本系請先登出再以本系帳號登入。<br>` : ''}
      帳號：貴系網址代號，例如工工系 <code>inde</code>、本系 <code>${esc(d.id)}</code>（即 ${esc(String(d.url||'').replace(/^https?:\\/\\//,'').split('.')[0])}.fcu.edu.tw 的前段）。<br>
      密碼：預設為貴單位的<b>總機分機</b>（4 碼）；若已申請變更過，請用公共事務組公告的新密碼。
      忘記密碼或要變更密碼，請洽秘書處公共事務組。
    </div>
    <div class="fb-lg">
      <div class="fb-lg-f"><label>帳號</label>
        <input id="fb-lg-u" type="text" autocomplete="username" value="${esc(d.id)}" placeholder="例：inde"></div>
      <div class="fb-lg-f"><label>密碼（單位分機）</label>
        <input id="fb-lg-p" type="password" autocomplete="current-password" placeholder="例：3601"
               onkeydown="if(event.key==='Enter'){event.preventDefault();fbLogin();}"></div>
      <button class="fb-lg-go" onclick="fbLogin()"><i class="ti ti-login"></i> 登入</button>
    </div>
    <div class="fb-lg-err" id="fb-lg-err"></div>
  </div>`;
}

function fbWhoHtml(d){
  return `<div class="fb-who">
    <i class="ti ti-user-check" style="font-size:14px;"></i>
    ${fbIsAdmin()
      ? `<span class="adm">管理者</span><span>以 <b>${esc(FB_AUTH.u)}</b> 登入，可填寫任一系；目前編輯 <b>${esc(d.name)}</b></span>`
      : `<span>已登入 <b>${esc(d.name)}</b>（<b>${esc(FB_AUTH.u)}</b>）</span>`}
    <span class="fb-who-acts">
      <button class="fb-who-out" onclick="fbPwdToggle()"><i class="ti ti-key"></i> 變更密碼</button>
      <button class="fb-who-out" onclick="fbLogout()"><i class="ti ti-logout"></i> 登出</button>
    </span>
  </div>` + fbPwdHtml(d);
}
/* ==AUTH_JS_END== */
'''.replace('__SALT__', SALT).replace('__CONST__', CONST)

if '==AUTH_JS_START==' in html:
    html, n = re.subn(r'/\* ═+\n   改善回饋填寫分頁：登入門檻  ==AUTH_JS_START==.*?/\* ==AUTH_JS_END== \*/\n',
                      lambda _m: JS, html, count=1, flags=re.S)
    if not n:
        sys.exit('取代 AUTH_JS 區塊失敗，請檢查 health-check.html 是否被手改過')
else:
    anchor = ('/* ═══════════════════════════════════════════════════════\n'
              '   改善回饋填寫分頁（各系同仁回報處理狀況）  ==FEEDBACK_JS_START==')
    assert anchor in html, '找不到 JS 插入位置（==FEEDBACK_JS_START==）'
    html = html.replace(anchor, JS + '\n' + anchor, 1)

# ══════════════════════════════════════════════════════════════════
# 3. 在 renderFeedback() 裡掛上門檻與登入狀態列
# ══════════════════════════════════════════════════════════════════
GATE_OLD = "  FB_CUR = d.id;\n  const its = fbItems(d)"
GATE_NEW = ("  FB_CUR = d.id;\n"
            "  /* ==AUTH_GATE== 未登入或登入他系：只顯示登入卡 */\n"
            "  if(!fbCanEdit(d.id)){ el.innerHTML = fbLockHtml(d); fbBadge(d); return; }\n"
            "  const its = fbItems(d)")
if '==AUTH_GATE==' not in html:
    assert GATE_OLD in html, '找不到 renderFeedback 門檻插入位置'
    html = html.replace(GATE_OLD, GATE_NEW, 1)

WHO_OLD = "  let h = '';\n  h += `<div class=\"fb-notice\">"
WHO_NEW = "  let h = '';\n  h += fbWhoHtml(d);\n  h += `<div class=\"fb-notice\">"
if 'h += fbWhoHtml(d);' not in html:
    assert WHO_OLD in html, '找不到登入狀態列插入位置'
    html = html.replace(WHO_OLD, WHO_NEW, 1)

# ── 寫回（先備份） ──
bak = HC.with_suffix('.html.bak-auth-' + datetime.datetime.now().strftime('%Y%m%d%H%M'))
shutil.copyfile(HC, bak)
HC.write_text(html, encoding='utf-8', newline='')

print('已設定 %d 個學系的登入帳密（帳號＝網址代號、密碼＝單位分機）' % len(AUTH))
print('管理者：%s（密碼＝%s 分機），可編輯任一系' % (ADMIN_U, j['admin']['unit']))
print('分機表：%s（%s 抽出）' % (j['src'], j['built']))
print('備份：', bak.name)
print('檔案大小：', round(HC.stat().st_size / 1024), 'KB')
