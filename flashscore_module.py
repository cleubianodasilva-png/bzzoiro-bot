"""
Módulo Flashscore — Fonte complementar de dados de futebol ao vivo
Sem chave, gratuita, leve (HTTP puro, sem navegador)
"""
import requests, re, json

FLASH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0',
    'Accept': '*/*',
    'x-fsign': 'SW9D1eZo',
    'Origin': 'https://www.flashscore.com',
    'Referer': 'https://www.flashscore.com/',
    'Accept-Language': 'en',
}

FLASH_BASE = 'https://local-global.flashscore.ninja/2'

# Mapeamento de IDs de estatísticas Flashscore → nomes internos
STAT_MAP = {
    12: 'posse',
    34: 'chutes_tot',
    13: 'chutes_gol',
    16: 'escanteios',
    23: 'cartao_amarelo',
    21: 'faltas',
    17: 'impedimentos',
    15: 'faltas_livres',
    14: 'chutes_fora',
}

def _parse(text):
    """Parse flashscore format into list of dicts."""
    result = []
    if not text or len(text) < 3:
        return result
    for item in text.split('~'):
        if not item.strip():
            continue
        d = {}
        for p in item.split('¬'):
            if '÷' in p:
                k, v = p.split('÷', 1)
                d[k] = v
        if d:
            result.append(d)
    return result

def _get_int(val, default=0):
    try:
        return int(float(val.replace('%', '').strip()))
    except:
        return default

def get_jogos_flashscore(fids_existentes):
    """Busca jogos ao vivo de hoje via Flashscore."""
    jogos = []
    try:
        url = f'{FLASH_BASE}/x/feed/f_1_0_3_en_1'
        r = requests.get(url, headers=FLASH_HEADERS, timeout=10)
        if r.status_code != 200:
            print(f'[FLASHSCORE] HTTP {r.status_code}')
            return []
        
        data = r.text
        items = data.split('¬~')
        
        liga_atual = ''
        for item in items:
            if not item.strip():
                continue
            d = {}
            for p in item.split('¬'):
                if '÷' in p:
                    k, v = p.split('÷', 1)
                    d[k] = v
            
            # League header
            if 'ZA' in d and 'AA' not in d:
                liga_atual = d.get('ZA', '')
                continue
            
            # Match
            if 'AA' in d:
                status_code = d.get('AB', '')
                # Só ao vivo
                if status_code != '2':
                    continue
                
                # Extrai dados
                home = d.get('CX', d.get('FH', d.get('AA', '?')))
                away = d.get('FK', '?')
                
                if home == '?' or away == '?' or len(home) < 2:
                    continue
                
                fid = 'flash_' + d.get('AA', '')
                if fid in fids_existentes:
                    continue
                
                # Score
                sh = _get_int(d.get('AG', d.get('AE', 0)))
                sa = _get_int(d.get('AH', d.get('AF', 0)))
                
                # Minuto: AC = minuto atual
                minuto = _get_int(d.get('AC', 0))
                if minuto > 120 or minuto < 0:
                    minuto = 0
                
                # Período: CR = período (1=1º, 2=2º)
                period_code = d.get('CR', '1')
                periodo = 2 if period_code == '2' else 1
                
                # Liga (vem do bloco header anterior)
                liga = liga_atual if liga_atual else 'World'
                
                match_id = d.get('AA', '')
                
                jogo = {
                    'home': home,
                    'away': away,
                    'minuto': minuto,
                    'period': periodo,
                    'sh': sh,
                    'sa': sa,
                    'liga': liga,
                    'fid': fid,
                    'fid_raw': match_id,
                    'source': 'flashscore',
                    'odds_b365': {},
                    'odds_bano': {},
                    # Dados adicionais que podem ser usados
                    'flash_raw': d,
                }
                jogos.append(jogo)
        
        print(f'[FLASHSCORE] {len(jogos)} jogos ao vivo encontrados')
        return jogos
    
    except Exception as e:
        print(f'[FLASHSCORE ERRO] get_jogos: {e}')
        return []

def get_stats_flashscore(match_id):
    """Busca estatísticas detalhadas de uma partida via Flashscore."""
    stats = {}
    try:
        # Busca estatísticas
        url = f'{FLASH_BASE}/x/feed/df_st_1_{match_id}'
        r = requests.get(url, headers=FLASH_HEADERS, timeout=10)
        if r.status_code == 200 and len(r.text) > 2:
            items = _parse(r.text)
            for item in items:
                stat_id = _get_int(item.get('SD', 0))
                stat_name = STAT_MAP.get(stat_id, '')
                if stat_name:
                    home_val = item.get('SH', '0')
                    away_val = item.get('SI', '0')
                    
                    if stat_name == 'escanteios':
                        stats['escanteios_h'] = _get_int(home_val)
                        stats['escanteios_a'] = _get_int(away_val)
                    elif stat_name == 'chutes_tot':
                        stats['chutes_tot_h'] = _get_int(home_val)
                        stats['chutes_tot_a'] = _get_int(away_val)
                    elif stat_name == 'chutes_gol':
                        stats['chutes_gol_h'] = _get_int(home_val)
                        stats['chutes_gol_a'] = _get_int(away_val)
                    elif stat_name == 'posse':
                        stats['posse_h'] = _get_int(home_val) / 100.0
                        stats['posse_a'] = _get_int(away_val) / 100.0
                    elif stat_name == 'cartao_amarelo':
                        stats['yellow_cards_h'] = _get_int(home_val)
                        stats['yellow_cards_a'] = _get_int(away_val)
                    elif stat_name == 'chutes_fora':
                        stats['chutes_fora_h'] = _get_int(home_val)
                        stats['chutes_fora_a'] = _get_int(away_val)
        
        # Busca eventos (gols, cartões vermelhos)
        url2 = f'{FLASH_BASE}/x/feed/df_sui_1_{match_id}'
        r2 = requests.get(url2, headers=FLASH_HEADERS, timeout=10)
        if r2.status_code == 200 and len(r2.text) > 2:
            items = _parse(r2.text)
            red_h = 0
            red_a = 0
            for item in items:
                event_type = item.get('IK', '')
                team = _get_int(item.get('IA', 0))
                if event_type == 'Red Card':
                    if team == 1:
                        red_h += 1
                    elif team == 2:
                        red_a += 1
            stats['red_cards_h'] = red_h
            stats['red_cards_a'] = red_a
        
        # Preenche defaults
        stats.setdefault('escanteios_h', 0)
        stats.setdefault('escanteios_a', 0)
        stats.setdefault('chutes_tot_h', 0)
        stats.setdefault('chutes_tot_a', 0)
        stats.setdefault('chutes_gol_h', 0)
        stats.setdefault('chutes_gol_a', 0)
        stats.setdefault('chutes_fora_h', 0)
        stats.setdefault('chutes_fora_a', 0)
        stats.setdefault('posse_h', 0.0)
        stats.setdefault('posse_a', 0.0)
        stats.setdefault('red_cards_h', 0)
        stats.setdefault('red_cards_a', 0)
        stats.setdefault('yellow_cards_h', 0)
        stats.setdefault('yellow_cards_a', 0)
        
        # Favorito pelo chutes
        total_h = stats.get('chutes_tot_h', 0)
        total_a = stats.get('chutes_tot_a', 0)
        if total_h > 0 or total_a > 0:
            stats['fav_side'] = 'h' if total_h >= total_a else 'a'
        
        return stats
    
    except Exception as e:
        print(f'[FLASHSCORE-STATS ERRO] {match_id}: {e}')
        return {}

def get_odds_flashscore(match_id):
    """Busca odds via Flashscore."""
    # Flashscore não retorna odds no mesmo formato direto
    # Usamos o fallback normal (apifootball/odds API) para odds
    return {}


if __name__ == '__main__':
    # Teste
    jogos = get_jogos_flashscore(set())
    for j in jogos:
        print(f'  {j["home"]} x {j["away"]} | {j["sh"]}x{j["sa"]} | {j["minuto"]}min | {j["liga"]}')
        if j.get('fid_raw'):
            stats = get_stats_flashscore(j['fid_raw'])
            if stats:
                print(f'    Escanteios: {stats.get("escanteios_h")}x{stats.get("escanteios_a")} | '
                      f'Chutes: {stats.get("chutes_tot_h")}x{stats.get("chutes_tot_a")} | '
                      f'Chutes Gol: {stats.get("chutes_gol_h")}x{stats.get("chutes_gol_a")} | '
                      f'Posse: {stats.get("posse_h",0)*100:.0f}%/{stats.get("posse_a",0)*100:.0f}% | '
                      f'Vermelhos: {stats.get("red_cards_h")}x{stats.get("red_cards_a")}')