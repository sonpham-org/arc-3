// Author: Claude Opus 5
// Date: 03-September-2026
// PURPOSE: Give every page served from docs/ a favicon that is one of the 25 official
//   ARC-AGI-3 games, picked at random per load, using the 64x64 board thumbnails already
//   shipped at static/img/games/<id>.png for the games grid. The site declared no icon at
//   all and /favicon.ico is 403'd by the oauth2-proxy in front of Caddy, so every tab
//   showed the browser default globe.
// SRP/DRY check: Pass - sets the icon link and nothing else; reuses the existing
//   thumbnails rather than generating or storing a second set of images.

// The official subset of static/games/manifest.json (category "official"). Inlined rather
// than fetched: the manifest is 877 entries and the icon should be set on the first
// paint, not after a round trip. Regenerate from the repo root with:
//   python3 -c "import json;print(chr(10).join(sorted(g['id'] for g in json.load(open('docs/static/games/manifest.json')) if g.get('category')=='official')))"
const OFFICIAL_GAMES = [
  "ar25-0c556536",
  "bp35-0a0ad940",
  "cd82-fb555c5d",
  "cn04-2fe56bfb",
  "dc22-fdcac232",
  "ft09-0d8bbf25",
  "g50t-5849a774",
  "ka59-38d34dbb",
  "lf52-271a04aa",
  "lp85-305b61c3",
  "ls20-9607627b",
  "m0r0-492f87ba",
  "r11l-495a7899",
  "re86-8af5384d",
  "s5i5-18d95033",
  "sb26-7fbdac44",
  "sc25-635fd71a",
  "sk48-d8078629",
  "sp80-589a99af",
  "su15-1944f8ab",
  "tn36-ef4dde99",
  "tr87-cd924810",
  "tu93-0768757b",
  "vc33-5430563c",
  "wa30-ee6fef47",
];

(function setGameFavicon() {
  try {
    const id = OFFICIAL_GAMES[Math.floor(Math.random() * OFFICIAL_GAMES.length)];
    // Reuse the markup's own link element when there is one, so the static fallback in
    // <head> is replaced rather than competing with a second icon of equal rank.
    let link = document.querySelector('link[rel="icon"]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.type = "image/png";
    link.href = "./static/img/games/" + id + ".png";
  } catch (e) {
    // A missing icon is the status quo, not a reason to break the page.
  }
})();
