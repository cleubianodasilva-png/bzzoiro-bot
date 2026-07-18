#!/usr/bin/env python3
import os, json, requests, time, hashlib, re, unicodedata
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# CONFIGURA\u00c7\u00c3O TELEGRAM
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "8949519269:AAH4PcbSHnrTXoFEk8e8zfkJ5BLi0mlLg0w")
CHAT_ID  = "-1003843430798" # GRUPO BZZOIRO -> Agora SOKKERPRO
CHAT_IDS = [CHAT_ID]

BRT = timezone(timedelta(hours=-3))

# CONFIGURA\u00c7\u00c3O GITHUB (MEM\u00d3RIA)
GITHUB_TOKEN = os.getenv("GH_PAT", "")
GITHUB_REPO  = "cleubianodasilva-png/bot-sokkerpro"
SENT_API_PATH = "sent_live_signals.json"
RESULTADO_API_PATH = "resultados.json"
PERFORMANCE_API_PATH = "performance.json"
LAST_UPDATE_FILE = "last_update.json"

# API SOKKERPRO
SOKKERPRO_URL = "https://m2.sokkerpro.com/livescores"
_CACHED_DATA = None

def _get_data():
    global _CACHED_DATA
    if _CACHED_DATA is None:
        try:
            r = requests.get(SOKKERPRO_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            _CACHED_DATA = r.json()
        except Exception as e:
            print(f"[SKP] Erro ao buscar dados: {e}")
            return None
    return _CACHED_DATA

def _get_float(val, default=0.0):
    if not val or str(val).strip() in ('', 'None'): return default
    try: return float(str(val).split('#')[0].strip())
    except: return default

def _get_int(val, default=0):
    if not val or str(val).strip() in ('', 'None'): return default
    try: return int(float(str(val)))
    except: return default

def get_jogos_sokkerpro(fids_existentes):
    data = _get_data()
    if not data: return []
    jogos = []
    try:
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                fid = str(fix.get('fixtureId', ''))
                if not fid or fid in fids_existentes: continue
                
                minuto = _get_int(fix.get('minute', 0))
                period = _get_int(fix.get('period', 0))
                
                jogos.append({
                    "fid": fid,
                    "home": fix.get('home_team_name', 'Home'),
                    "away": fix.get('away_team_name', 'Away'),
                    "minuto": minuto,
                    "period": period,
                    "sh": _get_int(fix.get('home_score', 0)),
                    "sa": _get_int(fix.get('away_score', 0)),
                    "liga": fix.get('league_name', 'Liga'),
                    "source": "sokkerpro"
                })
    except: pass
    return jogos

def get_stats_sokkerpro(fid_raw, home="", away=""):
    data = _get_data()
    if not data: return {}
    try:
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                if str(fix.get('fixtureId', '')) == str(fid_raw):
                    return {
                        "chutes_tot_h": _get_int(fix.get('home_shots_total', 0)),
                        "chutes_tot_a": _get_int(fix.get('away_shots_total', 0)),
                        "chutes_gol_h": _get_int(fix.get('home_shots_on_target', 0)),
                        "chutes_gol_a": _get_int(fix.get('away_shots_on_target', 0)),
                        "escanteios_h": _get_int(fix.get('home_corner_kicks', 0)),
                        "escanteios_a": _get_int(fix.get('away_corner_kicks', 0)),
                        "ataques_perigosos_h": _get_int(fix.get('home_dangerous_attacks', 0)),
                        "ataques_perigosos_a": _get_int(fix.get('away_dangerous_attacks', 0)),
                        "red_cards_h": _get_int(fix.get('home_red_cards', 0)),
                        "red_cards_a": _get_int(fix.get('away_red_cards', 0))
                    }
    except: pass
    return {}

def get_odds_sokkerpro(fid_raw):
    data = _get_data()
    if not data: return (None, None)
    try:
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                if str(fix.get('fixtureId', '')) == str(fid_raw):
                    oh = _get_float(fix.get('odds_home_win'))
                    oa = _get_float(fix.get('odds_away_win'))
                    return (oh, oa)
    except: pass
    return (None, None)

# --- REPLICANDO FUN\u00c7\u00d5ES DE LAYOUT E L\u00d3GICA ---

def analisar_e_disparar(game, stats, p, m, sh, sa, odd_h, odd_a, sent_vistos):
    try:
        oh = float(odd_h) if odd_h else 3.0
        oa = float(odd_a) if odd_a else 3.0
        fav_side = "h" if oh < oa else "a"
    except: fav_side = "h"

    fav_gols = sh if fav_side == "h" else sa
    adv_gols = sa if fav_side == "h" else sh
    red_fav = stats.get(f"red_cards_{fav_side}", 0)
    
    # 1. OVER GOL INTERVALO (HT)
    if p == 1 and 15 <= m <= 27:
        if sh == 0 and sa == 0 and red_fav == 0:
            atq_p = stats.get("ataques_perigosos_h", 0) + stats.get("ataques_perigosos_a", 0)
            ch_alvo = stats.get("chutes_gol_h", 0) + stats.get("chutes_gol_a", 0)
            if atq_p >= 15 and ch_alvo >= 1:
                return "HT", "Over 0.5 Gols HT"

    # 2. OVER GOL PARTIDA (FT)
    if p == 2 and 55 <= m <= 75:
        if (fav_gols <= adv_gols) and (adv_gols - fav_gols <= 1) and red_fav == 0:
            total_gols = sh + sa
            return "OVERGOAL", f"Mais de {total_gols + 0.5} Gols"

    # 3. AMBAS MARCAM (BTTS)
    if p == 2 and 55 <= m <= 75:
        if (sh + sa == 1) and (fav_gols == 0 and adv_gols == 1) and red_fav == 0:
            return "BTTS", "Ambas Marcam"

    # 4. OVER 1.5 GOLS PARTIDA
    if p == 2 and 55 <= m <= 75:
        if (sh + sa == 1) and (fav_gols == 0 and adv_gols == 1) and red_fav == 0:
            return "OFT", "Mais de 1.5 Gols"

    # 5. ESCANTEIO HT
    if p == 1 and 32 <= m <= 38:
        if (fav_gols <= adv_gols) and red_fav == 0:
            return "CORNER_HT", "Escanteio HT"

    # 6. ESCANTEIO FT
    if p == 2 and 82 <= m <= 88:
        if (fav_gols <= adv_gols) and red_fav == 0:
            return "CORNER_FT", "Escanteio FT"

    return None, None

def msg_universal(home, away, minuto, liga, n, mercado, entrada, placar, extra_val=None, cantos_atual=0, stats=None, sh=0, sa=0, fav_final="h", odd_h=None, odd_a=None):
    if "CORNER" in mercado or "ESCANTEIO" in mercado:
        cantos_atual = (stats.get("escanteios_h",0) + stats.get("escanteios_a",0)) if stats else 0
        linha = cantos_atual + 0.5
        entrada = f"Mais de {linha}🚩"
    if mercado in ("HT", "BTTS", "OVERGOAL"):
        entrada = str(entrada).rstrip() + "⚽️"

    titles = {
        "HT": "⚽️🔥OVER GOL INTERVALO🔥⚽️",
        "BTTS": "⚽️🔥AMBAS MARCAM🔥⚽️",
        "OFT": "⚽️🔥OVER 1.5 GOLS PARTIDA🔥⚽️",
        "OVERGOAL": "⚽️🔥OVER GOL PARTIDA🔥⚽️",
        "CORNER_HT": "🚩🔥ESCANTEIO ÁSIAT/LMT HT🔥🚩",
        "CORNER_FT": "🚩🔥ESCANTEIO ÁSIAT/LMT FT🔥🚩",
    }
    title = titles.get(mercado, f"🚩🔥{mercado}🔥🚩")
    sep = "━━━━━━━━━━━━━━━━━━━━"
    
    stats = stats or {}
    ch_h, ch_a = stats.get("chutes_tot_h", 0), stats.get("chutes_tot_a", 0)
    al_h, al_a = stats.get("chutes_gol_h", 0), stats.get("chutes_gol_a", 0)
    cn_h, cn_a = stats.get("escanteios_h", 0), stats.get("escanteios_a", 0)
    ap_h, ap_a = stats.get("ataques_perigosos_h", 0), stats.get("ataques_perigosos_a", 0)

    fav_nome = home if fav_final == "h" else away
    atq_fav = ap_h if fav_final == "h" else ap_a
    min_f = float(minuto) if minuto and float(minuto) > 0 else 1.0
    appm_val = atq_fav / min_f

    # APPM numérico + Alerta de Ritmo
    pressao_str = f"{appm_val:.2f}"
    if appm_val >= 1.2: alerta = "Partida Com Ritmo Intenso."
    elif appm_val >= 0.8: alerta = "Partida Com Ritmo Moderado."
    elif appm_val >= 0.5: alerta = "Partida Com Ritmo Médio."
    elif appm_val >= 0.3: alerta = "Partida Com Ritmo Fraco."
    else: alerta = "Partida Com Ritmo Lento."

    msg = (
        "<b>OPORTUNIDADE DETECTADA:</b>\n"
        + sep + "\n"
        + "<b>" + title + "</b>\n"
        + sep + "\n"
        + "<b>⚽️ Placar: " + str(placar) + "</b>\n"
        + "<b>🌍 Liga: " + str(liga) + "</b>\n"
        + "<b>📡 " + str(home) + " x " + str(away) + "</b>\n"
        + "<b>⏰️ Minuto: " + str(minuto) + "'</b>\n"
        + sep + "\n"
        + "<b>📊 Estatísticas ao Vivo da Partida:</b>\n"
        + "<b>🚀 Chutes Totais: " + str(ch_h) + " | " + str(ch_a) + "</b>\n"
        + "<b>🎯 Chutes No Alvo: " + str(al_h) + " | " + str(al_a) + "</b>\n"
        + "<b>⚔️ Ataques Perigosos: " + str(ap_h) + " | " + str(ap_a) + "</b>\n"
        + "<b>🚩 Escanteios: " + str(cn_h) + " | " + str(cn_a) + "</b>\n"
        + sep + "\n"
        + "<b>💡 Análise Técnica da Partida:</b>\n"
        + "<b>🎯 Favorito: " + fav_nome + "</b>\n"
        + "<b>🔥 Pressão APPM:</b><b>⚠️" + pressao_str + "⚠️</b>\n"
        + "<b>🚨 Alerta: " + alerta + "</b>\n"
        + sep + "\n"
        + "<b>📌 Entrada: " + str(entrada) + "</b>\n"
        + "<b>💰 ODD Recomendada: 1.70+</b>\n"
        + sep + "\n"
        + "🔔<b>Jogue com Responsabilidade</b>🔔"
    )
    return msg

def send_telegram(msg, home="", away=""):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    b365 = "https://www.bet365.bet.br/#/AX/"
    pari = "https://paripesa.com/en/live/football/"
    payload["reply_markup"] = json.dumps({"inline_keyboard": [[
        {"text": "\ud83d\udcaaBET365\ud83d\udcaa", "url": b365},
        {"text": "\ud83d\udd35PARIPESA\ud83d\udd35", "url": pari}
    ]]})
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get("result", {}).get("message_id")
    except: return None

def _github_headers():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

def load_sent():
    if not GITHUB_TOKEN: return {}
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SENT_API_PATH}"
        r = requests.get(url, headers=_github_headers(), timeout=8)
        if r.status_code == 200:
            import base64
            content = base64.b64decode(r.json()['content']).decode()
            return json.loads(content)
    except: pass
    return {}

def save_sent(sent):
    if not GITHUB_TOKEN: return
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SENT_API_PATH}"
        r_get = requests.get(url, headers=_github_headers(), timeout=8)
        sha = r_get.json().get("sha") if r_get.status_code == 200 else None
        import base64
        content = base64.b64encode(json.dumps(sent).encode()).decode()
        payload = {"message": "update sent signals [skip ci]", "content": content}
        if sha: payload["sha"] = sha
        requests.put(url, headers=_github_headers(), json=payload, timeout=8)
    except: pass

def run():
    print("[Iniciando SOKKERPRO - Layout ORIGINAL]")
    sent = load_sent()
    jogos = get_jogos_sokkerpro(set())
    print(f"[SKP] {len(jogos)} jogos ao vivo")
    
    for j in jogos:
        fid = j['fid']
        h, a, m, p = j['home'], j['away'], j['minuto'], j['period']
        sh, sa, liga = j['sh'], j['sa'], j['liga']
        
        stats = get_stats_sokkerpro(fid, h, a)
        oh, oa = get_odds_sokkerpro(fid)
        
        mercado, entrada = analisar_e_disparar(j, stats, p, m, sh, sa, oh, oa, sent)
        
        if mercado:
            chave = f"{fid}_{mercado}"
            if chave not in sent:
                fav = "h" if (oh or 3) < (oa or 3) else "a"
                msg = msg_universal(h, a, m, liga, 0, mercado, entrada, f"{sh}x{sa}", None, stats.get("escanteios_h",0)+stats.get("escanteios_a",0), stats, sh, sa, fav, oh, oa)
                mid = send_telegram(msg, h, a)
                if mid:
                    sent[chave] = {"mid": mid, "time": time.time()}
                    print(f"[ENVIADO] {h} x {a} ({mercado})")

    save_sent(sent)
    print("Finalizado.")

if __name__ == "__main__":
    run()