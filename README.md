# AI Architect Mastery — GitHub Pages site

Yksisivuinen laskeutumissivu AAM-brändille. Mukailee DIM-sivuston
(https://dataintegrationmastery.com) rakennetta, mutta käyttää tummempaa
ilmettä C008-presentaatioiden hengessä.

## Rakenne

```
gh-pages/
├── index.html                 # Yksisivuinen laskeutumissivu
├── css/style.css              # Tumma teema (jaetut brändifontit + värit)
├── js/main.js                 # Navi, YouTube-facade, tracking-hook
├── assets/
│   └── images/
│       ├── logo.png
│       └── backgrounds/kangas-8.jpg
├── sitemap.xml                # Yksisivuinen sitemap
├── robots.txt                 # Estää indeksoinnin kunnes domain ohjattu
├── CNAME.example              # Nimetään CNAME:ksi vasta kun domain ohjataan
└── .github/workflows/deploy.yml
```

## Sivun sisältö (ylhäältä alas)

1. **Header** — sticky-navi, logo + brändinimi, mobiilivalikko
2. **Hero** — otsikko, tagline ("From Developer to AI Architect"), CTA-painikkeet
3. **Intro Video** — YouTube-facade (lazy load); päivitä `data-video-id`
   lopullisella video-ID:llä
4. **Methodology** — PRD → PLAN → TASK → IMPLEMENTATION + neljä arvolausetta
5. **Courses** — featured: GH-300 sertifikaattivalmistautuminen (C008);
   lisäksi pipeline-kortit (Intro to Vibe Coding, Mastering Vibe Coding,
   Vibe Coding for Integration)
6. **Audience** — kenelle AAM on ja kenelle ei
7. **Instructor** — Ari Vilkman, maininta DIM-sisarbrändistä, LinkedIn-linkki
8. **Contact** — sosiaaliset linkit ja sähköposti
9. **Footer**

## Brändi & ilme

- **Fontit:** Roboto Slab (otsikot) + Lato (leipäteksti) — `/docs/rules/shared-visual-theme.md`
- **Värit:** Jaetut brändivärit (`#A55A82` heading, `#5A6B8A` accent) sovitettu
  tumman taustan päälle — heading nostettu `#C77BA5`:ksi WCAG AA:n täyttämiseksi
- **Taustakuva:** `assets/images/backgrounds/kangas-8.jpg` (sama kangas kuin
  DIM:llä; tumma overlay päällä)
- **Kortit:** Tummansininen läpikuultava `rgba(28, 32, 50, 0.92)`, magenta-reuna

## Domain (aiarchitectmastery.com)

- Domain on rekisteröity Namecheapissa, **DNS:ää ei ole vielä ohjattu**
  GitHub Pagesiin
- `robots.txt` estää toistaiseksi kaikki crawlerit
- `CNAME.example` → nimeä `CNAME` ja commitoi vasta kun domain ohjataan
- Canonical-, OG- ja sitemap-URL:it käyttävät jo `https://aiarchitectmastery.com/`
  → kun DNS aktivoidaan, mitään ei tarvitse muuttaa koodissa

## Paikallinen esikatselu

```bash
cd gh-pages
python3 -m http.server 8080
# Avaa http://localhost:8080
```

## Käyttöönotto GitHub Pagesiin

Kaksi tapaa:

**A) Oma erillinen repo (suositus):**
1. Luo uusi public repo, esim. `AIArchitectMastery/aiarchitectmastery.github.io`
2. Kopioi `gh-pages/`-kansion sisältö repon juureen
3. Settings → Pages → Source: GitHub Actions
4. Nimeä `CNAME.example` → `CNAME` kun olet valmis ohjaamaan domainin
5. Workflow `.github/workflows/deploy.yml` ajaa automaattisesti

**B) Sama repo, alikansio:**
- Aktivoi `.github/workflows/deploy.yml` ja muuta `path: "."` →
  `path: "./gh-pages"`

## TODO ennen julkaisua

- [ ] Päivitä intro-videon YouTube-ID (`data-video-id` index.html:ssä)
- [ ] Lisää Ari:n valokuva: `assets/images/instructor-ari.jpg` ja korvaa
  `.instructor-photo`-paikkamerkki kuvalla
- [ ] Lisää lopulliset Udemy-linkit GH-300-kortin CTA-painikkeisiin
- [ ] Wire MailerLite-lomake yhteystieto-osioon
- [ ] Lisää AAM:n omat sosiaalisen median linkit (LinkedIn-yritys,
  YouTube, Instagram) kun kanavat on luotu
- [ ] Lisää GDPR cookie-banneri ennen GA4 / Google Ads / Meta Pixel
  -tagien aktivointia
- [ ] Korvaa `robots.txt` `Disallow:`-rivi sallivaksi kun domain on live
- [ ] Validoi structured data Googlen Rich Results -työkalulla
