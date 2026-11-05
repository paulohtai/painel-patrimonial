// Rede primeiro, cache como reserva: o painel sempre mostra a versão mais nova
// quando há internet e continua abrindo sem internet.
const VERSAO = "pp-v9";
const BASE = ["./", "index.html", "manifest.webmanifest", "data/mercado.json", "data/ofertas.json",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSAO).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSAO).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const chave = url.origin === location.origin ? new Request(url.origin + url.pathname) : req;
  e.respondWith(
    fetch(req).then(res => {
      if (res && (res.ok || res.type === "opaque")) {
        const copia = res.clone();
        caches.open(VERSAO).then(c => c.put(chave, copia)).catch(() => {});
      }
      return res;
    }).catch(() => caches.match(chave).then(r => r || caches.match("index.html")))
  );
});
