# -*- coding: utf-8 -*-
"""
Собирает сайт из template.html.

Секреты берутся из переменных окружения (на GitHub — из Secrets),
а при локальном запуске — из файла secrets.local.json, который
лежит в .gitignore и никогда не попадает в репозиторий.

Главное: логин и пароль НЕ подставляются в страницу. Они работают
только как ключ шифрования. В собранный файл уезжает шифроблок.
"""
import base64, hashlib, json, os, pathlib, re, shutil, sys, unicodedata
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITER = 600000                      # итераций PBKDF2
ROOT = pathlib.Path(__file__).resolve().parent
OUT  = ROOT / "_site"
ASSETS = ["bg.jpg", "60_dark_and_stormy.mp3"]

# ---------- чтение секретов ----------
_local = {}
_local_path = ROOT / "secrets.local.json"
if _local_path.exists():
    _local = json.loads(_local_path.read_text(encoding="utf-8"))

def secret(name, required=False):
    val = os.environ.get(name) or _local.get(name) or ""
    val = val.strip()
    if required and not val:
        sys.exit(f"ОШИБКА: не задан секрет {name}")
    return val

LOGIN         = secret("SITE_LOGIN", required=True)
PASSWORD      = secret("SITE_PASSWORD", required=True)
RECOVERY_URL  = secret("RECOVERY_VIDEO")   # видео ДО входа — будет видно в коде страницы
VAULT_HTML    = secret("VAULT_HTML")       # целая страница после входа (шифруется)
VAULT_VIDEO   = secret("VAULT_VIDEO")      # видео ПОСЛЕ входа — шифруется
VAULT_TEXT    = secret("VAULT_TEXT")       # текст ПОСЛЕ входа — шифруется

# ---------- разбор ссылки YouTube ----------
def yt_id(url):
    url = (url or "").strip()
    if not url:
        return ""
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", url):
        return url
    # Саму ссылку не печатаем: логи сборки публичного репозитория видны всем,
    # а обрезанный кусок секрета GitHub уже не маскирует.
    sys.exit("ОШИБКА: не удалось разобрать ссылку YouTube (проверь значение секрета)")

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))

# ---------- содержимое закрытого экрана ----------
# Порядок источников:
#   1. секрет VAULT_HTML  — для публикации (содержимое не попадает в репозиторий)
#   2. файл vault.html    — для локальной работы (лежит в .gitignore)
#   3. секреты VAULT_VIDEO / VAULT_TEXT — простой вариант без файла
def video_block(url):
    vid = yt_id(url)
    if not vid:
        return ""
    src = f"https://www.youtube-nocookie.com/embed/{vid}?rel=0&amp;autoplay=1"
    return (f'<div class="v-video"><iframe src="{src}" title="" '
            'allow="autoplay; encrypted-media; picture-in-picture; fullscreen" '
            'referrerpolicy="no-referrer" allowfullscreen></iframe></div>')

def build_vault_html():
    source = None
    local = ROOT / "vault.html"
    example = ROOT / "vault.example.html"

    # Первый локальный запуск: создаём vault.html из образца, чтобы не
    # копировать вручную. На GitHub этого не делаем — там источник секрет.
    if not local.exists() and not VAULT_HTML and example.exists() \
            and not os.environ.get("GITHUB_ACTIONS"):
        shutil.copy2(example, local)
        print("Создан vault.html из образца — дальше правь его.")

    if VAULT_HTML:
        source, origin = VAULT_HTML, "секрет VAULT_HTML"
    elif local.exists():
        source, origin = local.read_text(encoding="utf-8"), "файл vault.html"

    if source is not None:
        print(f"Содержимое закрытого экрана: {origin}")
        # Подстановки, чтобы ссылка и текст могли оставаться секретами,
        # а вёрстка жила в файле.
        return (source.replace("{{VIDEO}}", video_block(VAULT_VIDEO))
                      .replace("{{TEXT}}", esc(VAULT_TEXT)))

    print("Содержимое закрытого экрана: секреты VAULT_VIDEO / VAULT_TEXT")
    parts = ['<div class="v-wrap">', video_block(VAULT_VIDEO)]
    if VAULT_TEXT:
        parts.append(f'<p class="v-note">{esc(VAULT_TEXT)}</p>')
    parts.append("</div>")
    return "".join(parts)

DOC_SHELL = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>—</title>
<style>
 html,body{margin:0;height:100%;background:#000;color:#c9c9c9;
   font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;}
 body{display:grid;place-items:center;padding:24px;}
 .v-wrap{width:min(1100px,100%);display:flex;flex-direction:column;gap:16px;align-items:center;}
 .v-video{width:100%;aspect-ratio:16/9;background:#000;border:1px solid rgba(255,255,255,.07);}
 .v-video iframe{width:100%;height:100%;border:0;display:block;}
 .v-note{margin:0;color:#8a8a8a;font-size:12px;letter-spacing:.08em;line-height:1.6;text-align:center;}
</style></head><body>
__BODY__
</body></html>"""

def ensure_document(html):
    """Целый документ пропускаем как есть, обрывок оборачиваем в страницу."""
    if re.search(r"<html[\s>]", html, re.I):
        return html
    return DOC_SHELL.replace("__BODY__", html)

def warn_if_blank(html):
    """Предупреждает, если после входа не будет видно ничего."""
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    body = re.sub(r"<(script|style)\b.*?</\1>", "", body, flags=re.S | re.I)
    media = re.search(r"<(img|iframe|video|audio|canvas|svg)\b", body, re.I)
    text = re.sub(r"<[^>]+>", "", body).strip()
    if not text and not media:
        print("ВНИМАНИЕ: после входа не будет видно ничего — экран останется чёрным.")
        print("          Проверь vault.html или секреты VAULT_VIDEO / VAULT_TEXT.")

# ---------- шифрование ----------
PAD_BLOCK = 4096   # длина шифротекста выдавала точный размер скрытой страницы

def pad(html):
    """Дополняет содержимое инертным комментарием до кратности PAD_BLOCK,
    чтобы по длине шифроблока нельзя было судить о размере страницы."""
    size = len(html.encode("utf-8"))
    target = ((size // PAD_BLOCK) + 1) * PAD_BLOCK
    need = target - size
    if need < 8:                      # на обёртку комментария нужно 7 байт
        need += PAD_BLOCK
    return html + "<!--" + ("." * (need - 7)) + "-->"

def encrypt(login, password, html):
    salt, iv = os.urandom(16), os.urandom(12)
    # NFC — чтобы кириллица считалась одинаково в Python и в браузере
    material = unicodedata.normalize(
        "NFC", login.strip().lower() + "\x00" + password).encode("utf-8")
    key = hashlib.pbkdf2_hmac("sha256", material, salt, ITER, 32)
    ct = AESGCM(key).encrypt(iv, pad(html).encode("utf-8"), None)
    return base64.b64encode(salt + iv + ct).decode()

vault_body = build_vault_html()
warn_if_blank(vault_body)
payload = encrypt(LOGIN, PASSWORD, ensure_document(vault_body))

# ---------- сборка ----------
html = (ROOT / "template.html").read_text(encoding="utf-8")
html = (html.replace("__PAYLOAD__", payload)
            .replace("__RECOVERY_ID__", yt_id(RECOVERY_URL))
            .replace("__ITER__", str(ITER)))

# Страховка: ни один секрет не должен оказаться в готовой странице.
# RECOVERY_VIDEO исключён намеренно — этот экран открывается до входа,
# и его id обязан быть в открытом виде, иначе видео не загрузится.
_guard = (("SITE_LOGIN", LOGIN), ("SITE_PASSWORD", PASSWORD),
          ("VAULT_VIDEO", VAULT_VIDEO), ("VAULT_TEXT", VAULT_TEXT),
          ("VAULT_HTML", VAULT_HTML))
_low = html.lower()
for name, value in _guard:
    # Короткие значения не проверяем подстрокой: обычное слово вроде «ты»
    # встречается в вёрстке и дало бы ложную тревогу.
    if len(value) >= 6 and (value in html or value.lower() in _low):
        sys.exit(f"ОШИБКА СБОРКИ: {name} попал в готовую страницу. Публикация остановлена.")

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
(OUT / "index.html").write_text(html, encoding="utf-8")
(OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
for a in ASSETS:
    src = ROOT / a
    if src.exists():
        shutil.copy2(src, OUT / a)
    else:
        print(f"внимание: нет файла {a}")

# Страховка: закрытые файлы не должны попасть в репозиторий
try:
    import subprocess
    tracked = subprocess.run(["git", "ls-files", "vault.html", "secrets.local.json"],
                             cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.split()
    for name in tracked:
        print(f"!!! ОПАСНО: {name} добавлен в git и уедет в репозиторий.")
        print(f"    Убрать:  git rm --cached {name}")
except Exception:
    pass

# Страховка: закрытая страница не должна оказаться среди опубликованных файлов
for leaked in OUT.rglob("vault*.html"):
    sys.exit(f"ОШИБКА СБОРКИ: {leaked.name} попал в публикацию. Остановлено.")

print(f"Готово: {OUT/'index.html'}  ({len(html)} символов, шифроблок {len(payload)})")
print("Логина, пароля и содержимого закрытого экрана в готовой странице нет — проверено.")
