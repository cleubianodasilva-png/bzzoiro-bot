"""
Módulo SokkerPro — Substitui a fonte Bzzoiro no bot.
API pública: https://m2.sokkerpro.com/livescores
Sem chave, sem token, sem limite de requisições.
"""
import requests, json, unicodedata, re

SOKKERPRO_URL = "https://m2.sokkerpro.com/livescores"

def _norm(s):
    return unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower().strip()

def _get_float(val, default=0.0):
    """Converte valor SokkerPro (pode vir '1.57#0' ou '17.50#0') pra float"""
    if not val or str(val).strip() in ('', 'None'):
        return default
    try:
        return float(str(val).split('#')[0].strip())
    except:
        return default

def _get_int(val, default=0):
    if not val or str(val).strip() in ('', 'None'):
        return default
    try:
        return int(float(str(val)))
    except:
        return default

def get_jogos_sokkerpro(fids_existentes):
    """
    Busca jogos ao vivo na SokkerPro.
    Retorna mesma estrutura que get_jogos_bzzoiro().
    """
    try:
        r = requests.get(SOKKERPRO_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        data = r.json()
        jogos = []
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                status = fix.get('status', '')
                if status not in ('1st', '2nd', 'HT'):
                    continue
                fid = "skp_" + str(fix.get('fixtureId', ''))
                if fid in fids_existentes:
                    continue
                sh = _get_int(fix.get('scoresLocalTeam', 0))
                sa = _get_int(fix.get('scoresVisitorTeam', 0))
                minuto = _get_int(fix.get('minute', 0))
                # Liga
                liga_nome = fix.get('leagueName', '') or ''
                if not liga_nome:
                    liga_nome = fix.get('countryName', 'Desconhecida')
                # Período
                if status == '1st':
                    period = 1
                elif status == 'HT':
                    period = 1
                elif status == '2nd':
                    period = 2
                else:
                    period = 1 if minuto <= 45 else 2
                # Nome dos times
                home = fix.get('localTeamName', '')
                away = fix.get('visitorTeamName', '')
                if not home or not away:
                    continue
                # Extrai odds do próprio fixture
                odd_h = _get_float(fix.get('XBET_VENCEDOR_HOME', 0))
                odd_d = _get_float(fix.get('XBET_VENCEDOR_DRAW', 0))
                odd_a = _get_float(fix.get('XBET_VENCEDOR_AWAY', 0))
                # Odds ao vivo BET365
                odd_live_h = _get_float(fix.get('BET365_VENCEDOR_1_LIVE', 0))
                odd_live_d = _get_float(fix.get('BET365_VENCEDOR_X_LIVE', 0))
                odd_live_a = _get_float(fix.get('BET365_VENCEDOR_2_LIVE', 0))
                # Se não tem XBET, tenta BET365 como fallback pra pré
                if not odd_h and odd_live_h:
                    odd_h, odd_d, odd_a = odd_live_h, odd_live_d, odd_live_a
                # Médias históricas pra favorito
                medias_h_gol = _get_float(fix.get('medias_home_goal', 0))
                medias_a_gol = _get_float(fix.get('medias_away_goal', 0))
                # Stats brutos iniciais
                tem_stats = bool(_get_int(fix.get('localShotsTotal', 0)) or _get_int(fix.get('visitorShotsTotal', 0)) or
                                _get_int(fix.get('localCorners', 0)) or _get_int(fix.get('visitorCorners', 0)))
                jogos.append({
                    "fid": fid,
                    "fid_raw": str(fix.get('fixtureId', '')),
                    "home": home,
                    "away": away,
                    "sh": sh,
                    "sa": sa,
                    "minuto": minuto,
                    "period": period,
                    "liga": liga_nome,
                    "source": "sokkerpro",
                    "odd_h": odd_h,
                    "odd_d": odd_d,
                    "odd_a": odd_a,
                    "odd_live_h": odd_live_h,
                    "odd_live_d": odd_live_d,
                    "odd_live_a": odd_live_a,
                    "medias_h_gol": medias_h_gol,
                    "medias_a_gol": medias_a_gol,
                    "tem_stats_brutos": tem_stats,
                    # Guarda o fixture inteiro pra extrair stats depois
                    "_raw": fix,
                })
        print(f"[SokkerPro] {len(jogos)} novos jogos")
        return jogos
    except Exception as e:
        print(f"[SokkerPro ERRO] get_jogos: {e}")
        return []

def get_stats_sokkerpro(fid_raw, home, away):
    """
    Extrai stats de um jogo SokkerPro.
    Como a SokkerPro já retorna tudo no mesmo payload,
    a gente busca de novo pra ter dados frescos.
    """
    try:
        r = requests.get(SOKKERPRO_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        data = r.json()
        # Busca o fixture pelo ID
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                if str(fix.get('fixtureId', '')) == fid_raw:
                    return _extrair_stats(fix, home, away)
        return {}
    except Exception as e:
        print(f"[SokkerPro ERRO] get_stats: {e}")
        return {}

def _extrair_stats(fix, home, away):
    """Extrai stats de um fixture SokkerPro no formato do bot."""
    stats = {}
    any_nonzero = False
    
    for prefix, side in [("local", "h"), ("visitor", "a")]:
        tot = _get_int(fix.get(f'{prefix}ShotsTotal', 0))
        stats[f"chutes_tot_{side}"] = tot
        if tot > 0: any_nonzero = True
        
        gol = _get_int(fix.get(f'{prefix}ShotsOnGoal', 0))
        stats[f"chutes_gol_{side}"] = gol
        if gol > 0: any_nonzero = True
        
        esc = _get_int(fix.get(f'{prefix}Corners', 0))
        stats[f"escanteios_{side}"] = esc
        if esc > 0: any_nonzero = True
        
        atq = _get_int(fix.get(f'{prefix}AttacksDangerousAttacks', 0))
        stats[f"ataques_perigosos_{side}"] = atq
        if atq > 0: any_nonzero = True
        
        pos = _get_int(fix.get(f'{prefix}BallPossession', 0))
        stats[f"posse_{side}"] = pos
        if pos > 0: any_nonzero = True
        
        # Chutes fora
        off = _get_int(fix.get(f'{prefix}ShotsOffGoal', 0))
        stats[f"chutes_fora_{side}"] = off
        
        # Faltas
        fls = _get_int(fix.get(f'{prefix}Fouls', 0))
        stats[f"faltas_{side}"] = fls
        
        # Cartões
        yel = _get_int(fix.get(f'{prefix}YellowCards', 0))
        stats[f"yellow_cards_{side}"] = yel
        red = _get_int(fix.get(f'{prefix}RedCards', 0))
        stats[f"red_cards_{side}"] = red
        
        # xG
        xg = _get_float(fix.get(f'{prefix}Xg', 0))
        stats[f"xg_{side}"] = xg
        
        # Ataques totais
        attacks = _get_int(fix.get(f'{prefix}AttacksAttacks', 0))
        stats[f"ataques_tot_{side}"] = attacks
        
        # DAPM
        dapm = _get_float(fix.get(f'{prefix}DapmTotal', 0))
        stats[f"dapm_{side}"] = dapm
        
        # Chutes dentro/fora da área
        inbox = _get_int(fix.get(f'{prefix}ShotsInsideBox', 0))
        stats[f"chutes_area_{side}"] = inbox
        outbox = _get_int(fix.get(f'{prefix}ShotsOutsideBox', 0))
        stats[f"chutes_fora_area_{side}"] = outbox
        
        # Passes
        passes_acc = _get_int(fix.get(f'{prefix}SuccessfulPasses', 0))
        stats[f"passes_certos_{side}"] = passes_acc
        passes_tot = _get_int(fix.get(f'{prefix}TotalPasses', 0))
        stats[f"passes_totais_{side}"] = passes_tot
    
    if not any_nonzero:
        return {}
    return stats

def get_stats_sokkerpro_by_name(home, away):
    """Fallback: busca stats na SokkerPro pelo nome dos times."""
    try:
        h_norm = _norm(home)
        a_norm = _norm(away)
        r = requests.get(SOKKERPRO_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        data = r.json()
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                h_nome = _norm(fix.get('localTeamName', ''))
                a_nome = _norm(fix.get('visitorTeamName', ''))
                if (h_busca in h_nome or h_nome in h_busca) and (a_busca in a_nome or a_nome in a_busca):
                    stats = _extrair_stats(fix, home, away)
                    if stats:
                        print(f"[SKP-NAME] Stats por nome OK: {fix.get('localTeamName')}x{fix.get('visitorTeamName')}")
                        return stats
        return {}
    except Exception as e:
        print(f"[SKP-NAME] Erro: {e}")
        return {}

def get_odds_sokkerpro(fid_raw, home, away):
    """
    Retorna (fav, odd_h, odd_d, odd_a) a partir das odds SokkerPro.
    Prioridade: BET365 live > XBET pré > médias históricas.
    """
    try:
        r = requests.get(SOKKERPRO_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        data = r.json()
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                if str(fix.get('fixtureId', '')) != fid_raw:
                    continue
                # Tenta BET365 live primeiro
                odd_h = _get_float(fix.get('BET365_VENCEDOR_1_LIVE', 0))
                odd_d = _get_float(fix.get('BET365_VENCEDOR_X_LIVE', 0))
                odd_a = _get_float(fix.get('BET365_VENCEDOR_2_LIVE', 0))
                if odd_h > 1 and odd_a > 1:
                    fav = "h" if odd_h <= odd_a else "a"
                    print(f"[ODDS-SKP] BET365 live: {home} x {away} -> Casa:{odd_h} Fora:{odd_a} Fav:{fav}")
                    return (fav, odd_h, odd_d, odd_a)
                # Fallback: XBET pré
                odd_h = _get_float(fix.get('XBET_VENCEDOR_HOME', 0))
                odd_d = _get_float(fix.get('XBET_VENCEDOR_DRAW', 0))
                odd_a = _get_float(fix.get('XBET_VENCEDOR_AWAY', 0))
                if odd_h > 1 and odd_a > 1:
                    fav = "h" if odd_h <= odd_a else "a"
                    print(f"[ODDS-SKP] XBET pré: {home} x {away} -> Casa:{odd_h} Fora:{odd_a} Fav:{fav}")
                    return (fav, odd_h, odd_d, odd_a)
                # Fallback: médias históricas
                medias_h = _get_float(fix.get('medias_home_goal', 0))
                medias_a = _get_float(fix.get('medias_away_goal', 0))
                if medias_h > 0 or medias_a > 0:
                    fav = "h" if medias_h >= medias_a else "a"
                    print(f"[ODDS-SKP] Médias históricas: {home} x {away} -> {medias_h:.1f}/{medias_a:.1f} Fav:{fav}")
                    return (fav, 1.0, 1.0, 1.0)
                print(f"[ODDS-SKP] {home} x {away} — sem odds disponíveis")
                return (None, None, None, None)
        return (None, None, None, None)
    except Exception as e:
        print(f"[ODDS-SKP] Erro: {e}")
        return (None, None, None, None)

def identificar_favorito_medias(fix):
    """Identifica favorito usando médias históricas (sem odds)."""
    h_gols = _get_float(fix.get('medias_home_goal', 0))
    a_gols = _get_float(fix.get('medias_away_goal', 0))
    h_chutes = _get_float(fix.get('medias_home_shots_total', 0))
    a_chutes = _get_float(fix.get('medias_away_shots_total', 0))
    h_atq = _get_float(fix.get('medias_home_dangerous_attacks', 0))
    a_atq = _get_float(fix.get('medias_away_dangerous_attacks', 0))
    h_posse = _get_float(fix.get('medias_home_possession', 0))
    a_posse = _get_float(fix.get('medias_away_possession', 0))
    
    if h_gols == 0 and a_gols == 0:
        return None
    
    h_score = h_gols * 2 + h_chutes * 0.1 + h_atq * 0.02 + h_posse * 0.01
    a_score = a_gols * 2 + a_chutes * 0.1 + a_atq * 0.02 + a_posse * 0.01
    
    if h_score > a_score * 1.1:
        return "h"
    elif a_score > h_score * 1.1:
        return "a"
    return None
def get_favorito_medias(fid_raw):
    """Busca fixture por ID e retorna favorito via médias históricas."""
    try:
        r = requests.get(SOKKERPRO_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        data = r.json()
        for cat in data['data']['sortedCategorizedFixtures']:
            for fix in cat['fixtures']:
                if str(fix.get('fixtureId', '')) == fid_raw:
                    return identificar_favorito_medias(fix)
    except:
        pass
    return None
