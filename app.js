/* ===========================================================================
   Jàkkaarloo — interface web (profils, sessions, actions rapides, langue).
   =========================================================================== */

// ------------------------------ Icônes SVG --------------------------------
const S = (p, o = 'stroke') =>
  `<svg viewBox="0 0 24 24" fill="${o === 'fill' ? 'currentColor' : 'none'}" stroke="${o === 'fill' ? 'none' : 'currentColor'}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">${p}</svg>`;
const ICONS = {
  leaf: '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 22V12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M12 14C12 9.6 8.4 6 4 6C4 10.4 7.6 14 12 14Z" fill="currentColor"/><path d="M12 12C12 7.6 15.6 4 20 4C20 8.4 16.4 12 12 12Z" fill="currentColor" opacity="0.85"/></svg>',
  menu: S('<path d="M4 6h16M4 12h16M4 18h16"/>'),
  plus: S('<path d="M12 5v14M5 12h14"/>'),
  adduser: S('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>'),
  cam: S('<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>'),
  close: S('<path d="M18 6 6 18M6 6l12 12"/>'),
  send: S('<path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/>'),
  chat: S('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'),
  trash: S('<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V6"/>'),
  pin: S('<path d="M21 10c0 7-9 12-9 12s-9-5-9-12a9 9 0 0 1 18 0Z"/><circle cx="12" cy="10" r="3"/>'),
  cloud: S('<path d="M17.5 17a4 4 0 0 0 0-8 6 6 0 0 0-11.5 1.7A3.5 3.5 0 0 0 6 17z"/><path d="M8 20l-.5 1.5M12 20l-.5 1.5M16 20l-.5 1.5"/>'),
  market: S('<path d="M3 9l1.5-4.5h15L21 9M3 9v10a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V9M3 9h18M8 13h8"/>'),
  diag: S('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>'),
  alert: S('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>'),
  seed: S('<path d="M12 20v-6"/><path d="M12 14c-4 0-6-3-6-7 4 0 6 3 6 7Z" fill="currentColor" stroke="none"/>'),
  translate: S('<path d="M4 5h9M8.5 5c0 5-3 9-6.5 11M5 9c0 3 3.5 5.5 7 6.5"/><path d="M14 20l4-9 4 9M15.5 17h5"/>'),
};
// Mascotte (badge à fond dégradé : feuilles blanches + visage vert foncé).
const MASCOT = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
  + '<path d="M12 21c-1.4-6-6-9-11-9 0 6 4.6 10 11 10Z" fill="#ffffff" opacity="0.55"/>'
  + '<path d="M12 20c6.6-4 10.4-10.4 10.4-18.4C15 2.6 10.4 9.8 12 20Z" fill="#ffffff"/>'
  + '<circle cx="13.7" cy="9.1" r="0.95" fill="#0a6b48"/><circle cx="17.2" cy="7.4" r="0.95" fill="#0a6b48"/>'
  + '<path d="M13.4 12c1.5 1 3.2 0.5 4.4-0.9" fill="none" stroke="#0a6b48" stroke-width="1.1" stroke-linecap="round"/></svg>';

const $ = (id) => document.getElementById(id);

// ------------------------------ État --------------------------------------
let currentUser = JSON.parse(localStorage.getItem("jak_user") || "null");
let currentSessionId = localStorage.getItem("jak_session") || null;
let currentLang = localStorage.getItem("jak_lang") || "fr";
let photoEnAttente = null;
let envoiEnCours = false;

// ------------------------------ Client API --------------------------------
const api = {
  async createUser(name, region, crops) {
    return (await fetch("/api/users", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, region, crops }) })).json();
  },
  async listUsers() { return (await fetch("/api/users")).json(); },
  async listSessions(uid) { return (await fetch(`/api/users/${uid}/sessions`)).json(); },
  async createSession(uid) { return (await fetch(`/api/users/${uid}/sessions`, { method: "POST" })).json(); },
  async getSession(uid, sid) { return (await fetch(`/api/users/${uid}/sessions/${sid}`)).json(); },
  async deleteSession(uid, sid) { return fetch(`/api/users/${uid}/sessions/${sid}`, { method: "DELETE" }); },
};

// ------------------------------ Utilitaires --------------------------------
function escapeHtml(s) { return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function inlineFmt(s) { return s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>"); }
function formatMarkdown(md) {
  const lines = escapeHtml(md).split("\n");
  let html = "", inList = false, para = [];
  const flushPara = () => { if (para.length) { html += "<p>" + inlineFmt(para.join(" ")) + "</p>"; para = []; } };
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flushPara(); closeList(); continue; }
    const bullet = line.match(/^(?:[-*]|\d+[.)])\s+(.*)$/);
    const heading = line.match(/^(#{1,3})\s+(.*)$/);
    if (bullet) { flushPara(); if (!inList) { html += "<ul>"; inList = true; } html += "<li>" + inlineFmt(bullet[1]) + "</li>"; }
    else if (heading) { flushPara(); closeList(); html += "<p><strong>" + inlineFmt(heading[2]) + "</strong></p>"; }
    else { closeList(); para.push(line); }
  }
  flushPara(); closeList();
  return html || "<p></p>";
}
function initiale(nom) { return (nom || "?").trim().charAt(0).toUpperCase() || "?"; }
function metaProfil(u) {
  const bits = [];
  if (u.region) bits.push(u.region);
  if (u.crops && u.crops.length) bits.push(u.crops.slice(0, 2).join(", ") + (u.crops.length > 2 ? "…" : ""));
  return bits.join(" · ");
}
function tempsRelatif(t) {
  if (!t) return "";
  const d = Date.now() / 1000 - t;
  if (d < 60) return "à l'instant";
  if (d < 3600) return `il y a ${Math.floor(d / 60)} min`;
  if (d < 86400) return `il y a ${Math.floor(d / 3600)} h`;
  return new Date(t * 1000).toLocaleDateString("fr-FR");
}

// ------------------------------ Icônes statiques ---------------------------
function poserIcones() {
  $("brand-logo").innerHTML = ICONS.leaf;
  $("topbar-logo").innerHTML = ICONS.leaf;
  $("modal-logo").innerHTML = MASCOT;
  $("ico-new").innerHTML = ICONS.plus;
  $("ico-new2").innerHTML = ICONS.plus;
  $("ico-adduser").innerHTML = ICONS.adduser;
  $("ico-menu").innerHTML = ICONS.menu;
  $("ico-lang").innerHTML = ICONS.translate;
  $("ico-cam").innerHTML = ICONS.cam;
  $("ico-close").innerHTML = ICONS.close;
  $("ico-send").innerHTML = ICONS.send;
}

// ------------------------------ Messages -----------------------------------
function clearMessages() { $("messages").innerHTML = ""; }
function scrollBas() { const m = $("messages"); m.scrollTop = m.scrollHeight; }

function showWelcome() {
  clearMessages();
  const nom = currentUser ? currentUser.name.split(" ")[0] : "";
  const region = (currentUser && currentUser.region) || "";
  const tags = (currentUser && currentUser.crops && currentUser.crops.length)
    ? currentUser.crops.map((c) => `<span class="tag">${escapeHtml(c)}</span>`).join(" ") : "";
  const div = document.createElement("div");
  div.className = "hero";
  div.innerHTML = `
    <span class="badge"><span class="dot"></span> Assistant multi-agents · FR / Wolof</span>
    <h1>Bonjour, <span class="accent">${escapeHtml(nom)}</span> <span class="sprout">${ICONS.leaf}</span></h1>
    <p class="hero-sub">Votre conseiller agricole IA pour le Sahel. Météo, marchés, diagnostic — en français ou en wolof.</p>
    <p class="section-label">ACTIONS RAPIDES</p>
    <div class="quick-actions">
      <button class="qa qa-green" data-qa="meteo"><span class="qa-ico">${ICONS.cloud}</span>
        <span class="qa-title">Consulter la météo</span><span class="qa-sub">Prévisions 7 jours & fenêtre de semis</span></button>
      <button class="qa qa-amber" data-qa="marche"><span class="qa-ico">${ICONS.market}</span>
        <span class="qa-title">Vérifier les prix du marché</span><span class="qa-sub">Prix comparés par marché</span></button>
      <button class="qa qa-rose" data-qa="photo"><span class="qa-ico">${ICONS.cam}</span>
        <span class="qa-title">Diagnostiquer une maladie</span><span class="qa-sub">Analyse indicative d'une photo</span></button>
    </div>
    ${currentUser ? `<div class="profil-actif">
      <div class="pa-label">PROFIL ACTIF</div>
      <div class="pa-row"><span class="pa-name">${escapeHtml(currentUser.name)}</span>
        ${region ? `<span class="pa-loc">${ICONS.pin} ${escapeHtml(region)}</span>` : ""}${tags}</div>
    </div>` : ""}`;
  $("messages").appendChild(div);
  div.querySelectorAll(".qa").forEach((b) => b.addEventListener("click", () => actionRapide(b.dataset.qa)));
}

function actionRapide(type) {
  const region = (currentUser && currentUser.region) || "ma région";
  const culture = (currentUser && currentUser.crops && currentUser.crops[0]) || "l'oignon";
  if (type === "meteo") envoyerTexte(`Va-t-il pleuvoir cette semaine à ${region} ? Dois-je semer ?`);
  else if (type === "marche") envoyerTexte(`Quels sont les prix du marché pour ${culture} en ce moment ?`);
  else if (type === "photo") $("input-photo").click();
}

function ajouterMessage(role, { texte = "", html = null, photoUrl = null } = {}) {
  const msg = document.createElement("div");
  msg.className = "msg " + role;
  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  if (role === "agent") avatar.innerHTML = MASCOT; else avatar.textContent = initiale(currentUser?.name);
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (photoUrl) { const img = document.createElement("img"); img.className = "photo"; img.src = photoUrl; bubble.appendChild(img); }
  const zone = document.createElement("div");
  if (html !== null) zone.innerHTML = html; else { zone.style.whiteSpace = "pre-wrap"; zone.textContent = texte; }
  bubble.appendChild(zone);
  msg.appendChild(avatar);
  if (role === "agent") {
    const col = document.createElement("div"); col.className = "msg-col";
    const nom = document.createElement("div"); nom.className = "msg-name"; nom.textContent = "Jàkkaarloo";
    col.appendChild(nom); col.appendChild(bubble); msg.appendChild(col);
  } else msg.appendChild(bubble);
  $("messages").appendChild(msg); scrollBas();
  return { bubble, zone };
}

// ------------------------------ Chips --------------------------------------
function renderChips() {
  const region = (currentUser && currentUser.region) || "Kaolack";
  const chips = [
    { t: `Va-t-il pleuvoir à ${region} ?`, ico: ICONS.cloud },
    { t: "Prix de l'oignon à Dakar", ico: ICONS.market },
    { t: "Diagnostiquer une maladie (photo)", ico: ICONS.cam, action: "photo" },
    { t: "Quand semer l'arachide ?", ico: ICONS.seed },
    { t: "Quel dosage de pesticide utiliser ?", ico: ICONS.alert },
  ];
  const row = $("chips-row"); row.innerHTML = "";
  for (const c of chips) {
    const b = document.createElement("button");
    b.className = "chip";
    b.innerHTML = `<span class="chip-ico">${c.ico}</span> ${escapeHtml(c.t)}`;
    b.addEventListener("click", () => c.action === "photo" ? $("input-photo").click() : envoyerTexte(c.t));
    row.appendChild(b);
  }
}

// ------------------------------ Sidebar : profils --------------------------
async function renderProfiles() {
  const users = await api.listUsers();
  const list = $("profiles-list"); list.innerHTML = "";
  for (const u of users) {
    const card = document.createElement("div");
    card.className = "profile-card" + (currentUser && u.id === currentUser.id ? " active" : "");
    const meta = metaProfil(u);
    card.innerHTML = `<span class="pc-avatar">${initiale(u.name)}</span>
      <div class="pc-body"><div class="pc-name">${escapeHtml(u.name)}</div>
      ${meta ? `<div class="pc-meta">${ICONS.pin}${escapeHtml(meta)}</div>` : ""}</div>`;
    card.addEventListener("click", () => choisirUser(u));
    list.appendChild(card);
  }
}

// ------------------------------ Sidebar : sessions -------------------------
async function refreshSessions() {
  if (!currentUser) return;
  $("sessions-label").textContent = "Sessions · " + currentUser.name.split(" ")[0];
  const sessions = await api.listSessions(currentUser.id);
  const list = $("sessions-list"); list.innerHTML = "";
  $("sessions-empty").hidden = sessions.length > 0;
  for (const s of sessions) {
    const item = document.createElement("div");
    item.className = "session-item" + (s.id === currentSessionId ? " active" : "");
    item.innerHTML = `<span class="session-icon">${ICONS.chat}</span>
      <div class="session-body"><div class="session-title">${escapeHtml(s.titre || "Conversation")}</div>
      <div class="session-time">${tempsRelatif(s.last_update_time)}</div></div>
      <button class="session-del" title="Supprimer">${ICONS.trash}</button>`;
    item.addEventListener("click", (e) => { if (e.target.closest(".session-del")) return; selectSession(s.id); fermerSidebarMobile(); });
    item.querySelector(".session-del").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("Supprimer cette conversation ?")) return;
      await api.deleteSession(currentUser.id, s.id);
      if (s.id === currentSessionId) { currentSessionId = null; localStorage.removeItem("jak_session"); showWelcome(); }
      refreshSessions();
    });
    list.appendChild(item);
  }
}

async function selectSession(sid) {
  currentSessionId = sid; localStorage.setItem("jak_session", sid);
  const data = await api.getSession(currentUser.id, sid);
  clearMessages();
  if (!data.messages || data.messages.length === 0) showWelcome();
  else for (const m of data.messages) {
    if (m.role === "agent") ajouterMessage("agent", { html: formatMarkdown(m.text) });
    else ajouterMessage("user", { texte: m.text + (m.has_image ? "\n(photo jointe)" : "") });
  }
  refreshSessions();
}

async function nouvelleConversation() {
  if (!currentUser) { ouvrirModalUser(true); return; }
  const s = await api.createSession(currentUser.id);
  currentSessionId = s.id; localStorage.setItem("jak_session", s.id);
  showWelcome(); await refreshSessions(); fermerSidebarMobile(); $("input-message").focus();
}

// ------------------------------ Utilisateur --------------------------------
function majUserUI() {
  if (!currentUser) return;
  $("topbar-sub").textContent = metaProfil(currentUser) || "Conseiller agricole IA";
}
async function ouvrirModalUser(peutAnnuler = false) {
  const zone = $("users-existants"); zone.innerHTML = "";
  const users = await api.listUsers();
  for (const u of users) {
    const b = document.createElement("button");
    b.className = "user-existant";
    b.innerHTML = `<span class="pc-avatar">${initiale(u.name)}</span>
      <div class="ue-body"><div class="ue-name">${escapeHtml(u.name)}</div>
      ${metaProfil(u) ? `<div class="ue-meta">${escapeHtml(metaProfil(u))}</div>` : ""}</div>`;
    b.addEventListener("click", () => choisirUser(u));
    zone.appendChild(b);
  }
  $("modal-title").textContent = users.length ? "Choisissez un profil" : "Bienvenue sur Jàkkaarloo";
  $("modal-close").hidden = !peutAnnuler;
  $("modal-user").hidden = false;
}
function fermerModalUser() { $("modal-user").hidden = true; }

async function choisirUser(u) {
  currentUser = { id: u.id, name: u.name, region: u.region || "", crops: u.crops || [] };
  localStorage.setItem("jak_user", JSON.stringify(currentUser));
  currentSessionId = null; localStorage.removeItem("jak_session");
  majUserUI(); fermerModalUser(); renderChips();
  await renderProfiles(); await refreshSessions();
  const sessions = await api.listSessions(currentUser.id);
  if (sessions.length) selectSession(sessions[0].id); else showWelcome();
}

// ------------------------------ Envoi --------------------------------------
function envoyerTexte(txt) { $("input-message").value = txt; envoyer(); }

async function envoyer() {
  if (envoiEnCours) return;
  const message = $("input-message").value.trim();
  if (!message && !photoEnAttente) return;
  if (!currentUser) { ouvrirModalUser(); return; }
  if (!currentSessionId) { const s = await api.createSession(currentUser.id); currentSessionId = s.id; localStorage.setItem("jak_session", s.id); }

  const hero = $("messages").querySelector(".hero"); if (hero) hero.remove();
  ajouterMessage("user", { texte: message, photoUrl: photoEnAttente ? photoEnAttente.dataUrl : null });

  const charge = { user_id: currentUser.id, session_id: currentSessionId, message, lang: currentLang,
    image_base64: photoEnAttente ? photoEnAttente.base64 : null, image_mime: photoEnAttente ? photoEnAttente.mime : null };
  $("input-message").value = ""; autoResize();
  photoEnAttente = null; $("input-photo").value = ""; $("apercu-photo").hidden = true;
  verrou(true);

  const { bubble } = ajouterMessage("agent", { texte: "" });
  bubble.querySelector("div").remove();
  const statut = document.createElement("div"); statut.className = "status-line";
  statut.innerHTML = 'Réflexion <span class="typing"><i></i><i></i><i></i></span>';
  const flux = document.createElement("div"); flux.style.whiteSpace = "pre-wrap";
  bubble.appendChild(statut); bubble.appendChild(flux);

  let texteComplet = "", aRecu = false;
  try {
    const rep = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(charge) });
    if (!rep.ok || !rep.body) throw new Error("HTTP " + rep.status);
    const reader = rep.body.getReader(); const dec = new TextDecoder(); let buf = "";
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      const blocs = buf.split("\n\n"); buf = blocs.pop();
      for (const bloc of blocs) {
        const ligne = bloc.split("\n").find((l) => l.startsWith("data: ")); if (!ligne) continue;
        const ev = JSON.parse(ligne.slice(6));
        if (ev.type === "status") statut.innerHTML = escapeHtml(ev.text) + ' <span class="typing"><i></i><i></i><i></i></span>';
        else if (ev.type === "delta") { if (!aRecu) { statut.remove(); aRecu = true; } texteComplet += ev.text; flux.textContent = texteComplet; scrollBas(); }
        else if (ev.type === "error") { statut.remove(); flux.textContent = "Une erreur est survenue. Réessayez."; console.error(ev.text); }
      }
    }
    if (aRecu) { flux.style.whiteSpace = ""; flux.innerHTML = formatMarkdown(texteComplet); }
    else { statut.remove(); flux.textContent = "(Pas de réponse.)"; }
  } catch (err) { statut.remove(); flux.textContent = "Connexion impossible. Vérifiez que le service tourne."; console.error(err); }
  finally { verrou(false); refreshSessions(); $("input-message").focus(); }
}
function verrou(a) { envoiEnCours = a; $("btn-send").disabled = a; }

// ------------------------------ Photo --------------------------------------
$("input-photo").addEventListener("change", () => {
  const f = $("input-photo").files[0]; if (!f) return;
  const fr = new FileReader();
  fr.onload = () => { const d = fr.result; photoEnAttente = { base64: d.split(",")[1], mime: f.type, dataUrl: d }; $("apercu-img").src = d; $("apercu-photo").hidden = false; };
  fr.readAsDataURL(f);
});
$("retirer-photo").addEventListener("click", () => { photoEnAttente = null; $("input-photo").value = ""; $("apercu-photo").hidden = true; });

// ------------------------------ Saisie -------------------------------------
function autoResize() { const t = $("input-message"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 150) + "px"; }
$("input-message").addEventListener("input", autoResize);
$("input-message").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(); } });
$("formulaire").addEventListener("submit", (e) => { e.preventDefault(); envoyer(); });

// ------------------------------ Langue -------------------------------------
$("lang-toggle").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-lang]"); if (!b) return;
  currentLang = b.dataset.lang; localStorage.setItem("jak_lang", currentLang);
  $("lang-toggle").querySelectorAll("button").forEach((x) => x.classList.toggle("active", x.dataset.lang === currentLang));
});

// ------------------------------ Sidebar / modal ----------------------------
$("btn-new").addEventListener("click", nouvelleConversation);
$("btn-new-2").addEventListener("click", nouvelleConversation);
$("btn-add-profile").addEventListener("click", () => ouvrirModalUser(true));
$("modal-close").addEventListener("click", fermerModalUser);
$("form-user").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nom = $("in-name").value.trim(); if (!nom) return;
  const region = $("in-region").value.trim();
  const crops = $("in-crops").value.split(",").map((c) => c.trim()).filter(Boolean);
  const u = await api.createUser(nom, region, crops);
  $("in-name").value = ""; $("in-region").value = ""; $("in-crops").value = "";
  choisirUser(u);
});
function toggleSidebar() {
  const sb = $("sidebar");
  if (window.matchMedia("(max-width: 768px)").matches) { const o = sb.classList.toggle("open"); $("scrim").hidden = !o; }
  else sb.classList.toggle("collapsed");
}
function fermerSidebarMobile() { $("sidebar").classList.remove("open"); $("scrim").hidden = true; }
$("btn-menu").addEventListener("click", toggleSidebar);
$("scrim").addEventListener("click", fermerSidebarMobile);

// ------------------------------ Démarrage ----------------------------------
async function init() {
  poserIcones();
  $("lang-toggle").querySelectorAll("button").forEach((x) => x.classList.toggle("active", x.dataset.lang === currentLang));
  renderChips();
  if (!currentUser) { showWelcome(); ouvrirModalUser(false); return; }
  majUserUI(); await renderProfiles(); await refreshSessions();
  if (currentSessionId) selectSession(currentSessionId);
  else { const s = await api.listSessions(currentUser.id); s.length ? selectSession(s[0].id) : showWelcome(); }
}
init();
