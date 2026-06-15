import requests
from datetime import datetime, timedelta, timezone
from config import HEVY_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# ==========================================
# 1. CONFIGURAÇÕES DA API E ROTINAS
# ==========================================
HEVY_API_URL_WORKOUTS = "https://api.hevyapp.com/v1/workouts"
HEVY_API_URL_ROUTINES = "https://api.hevyapp.com/v1/routines"

HEADERS_API = {
    "accept": "application/json", 
    "content-type": "application/json", 
    "api-key": HEVY_API_KEY
}

# Substitua pelos UUIDs exatos que você coletou
ROTINAS_IDS = {
    "Treino A": "a5013e79-cb4e-4872-9882-5e147c756d27",
    "Treino B": "e5729a7d-2ece-4d1e-8e58-e10239b8f093",
    "Treino C": "e9c0a23e-6b8d-4507-9c28-dba043540e91",
    "Treino D": "df62efd0-d1ed-4321-ae8d-0aeb8eb49237",
    "Treino E": "9e1f1270-c1c2-4e17-b106-ef629da9fcf9"
}

# ==========================================
# 2. CONFIGURAÇÕES DE HARDWARE E TARAS
# ==========================================
EQUIPMENT_CONFIG = {
    # Máquinas Articuladas
    "Press De Peito Iso-Lateral (Máquina)": {"type": "plate_loaded", "tara": 13.5},
    "Remadas Iso-Lateral (Máquina)": {"type": "plate_loaded", "tara": 22.6},
    "Leg Press 45º (Máquina)": {"type": "plate_loaded", "tara": 75.0},
    "Elevação Unilateral de Panturrilha em Pé (Máquina)": {"type": "plate_loaded", "tara": 30.4},
    
    # Cabos
    "Elevação Lateral Unilateral (Cabo)": {"type": "cable", "tara": 0.0},
    "Elevação Lateral (Cabo)": {"type": "cable", "tara": 0.0},
    "Rosca por Trás (Cabo)": {"type": "cable", "tara": 0.0},
    "Extensão de tríceps acima da cabeça (cabo)": {"type": "cable", "tara": 0.0},
    "Tríceps na Polia com Corda": {"type": "cable", "tara": 0.0},
    "Extensão de Tríceps Unilateral (Cabo)": {"type": "cable", "tara": 0.0},
    "Puxada Com Braços Esticados (Corda)": {"type": "cable", "tara": 0.0},
    "Puxada Com O Braço Reto (Corda)": {"type": "cable", "tara": 0.0},
    "Puxada Alta - Pegada Triângulo": {"type": "cable", "tara": 0.0},
    "Puxada Unilateral": {"type": "cable", "tara": 0.0},
    "Puxada Alta No Cabo": {"type": "cable", "tara": 0.0},
    "Retração De Manguito Supraespinhal": {"type": "cable", "tara": 0.0},
    "Rotação De Manguito Supraespinhal": {"type": "cable", "tara": 0.0},
    
    # Halteres
    "Supino Inclinado (Halter)": {"type": "dumbbell", "tara": 0.0},
    "Elevação Lateral (Halter)": {"type": "dumbbell", "tara": 0.0},
    "Rosca Martelo Alternada": {"type": "dumbbell", "tara": 0.0},
    "Remadas Dobradas (Halter)": {"type": "dumbbell", "tara": 0.0},
    "Rosca Scott (Halter)": {"type": "dumbbell", "tara": 0.0},
    
    # Barras e Máquinas de Pino
    "Levantamento Terra Romeno (Barra)": {"type": "barbell", "tara": 20.0},
    "Rosca Direta na Barra W": {"type": "barbell", "tara": 0.0},
    "Crucifixo no Voador (Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Aberturas Invertidas De Ombro Posterior (Na Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Rosca Scott (Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Cadeira Extensora (Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Cadeira Flexora (Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Puxada Alta na Polia (Máquina)": {"type": "machine_pin", "tara": 0.0},
}

# ==========================================
# 3. NÚCLEO MATEMÁTICO E SNAPPING
# ==========================================
def formatar_peso(peso):
    """Remove a casa decimal .0 para deixar o relatório mais limpo"""
    return str(peso).replace('.0', '') if isinstance(peso, float) and peso.is_integer() else str(peso)

def get_increment(eq_type):
    if eq_type in ["plate_loaded", "barbell"]: return 5.0
    if eq_type == "dumbbell": return 4.0
    if eq_type == "machine_pin": return 2.5
    if eq_type == "cable": return 2.26796
    return 1.0

def snap_weight(target_weight, config):
    eq_type, tara = config["type"], config["tara"]
    if eq_type in ["plate_loaded", "barbell"]:
        peso_anilhas = target_weight - tara
        if peso_anilhas <= 0: return tara
        return tara + (round(peso_anilhas / 5) * 5)
    elif eq_type == "cable":
        lb_factor = 2.26796
        return round(round(target_weight / lb_factor) * lb_factor, 1)
    elif eq_type == "dumbbell":
        return round(target_weight / 4) * 4
    elif eq_type == "machine_pin":
        return round(target_weight / 2.5) * 2.5
    return round(target_weight, 1)

def processar_progressao(exercise_title, top_peso, top_reps, back_peso=None, back_reps=None):
    config = EQUIPMENT_CONFIG.get(exercise_title.strip(), {"type": "standard", "tara": 0.0})
    eq_type = config["type"]
    incremento = get_increment(eq_type)
    
    motivo = "Na faixa de trabalho"
    
    if top_reps >= 9:
        novo_top_set = snap_weight(top_peso * 1.05, config)
        if novo_top_set <= top_peso: novo_top_set = round(top_peso + incremento, 1)
        motivo = "Meta batida no Top Set"
    elif top_reps >= 5:
        novo_top_set = top_peso
    else:
        novo_top_set = snap_weight(top_peso * 0.95, config) 
        motivo = "Abaixo da faixa (Deload)"
        
    if back_peso is not None and back_reps is not None:
        if back_reps >= 10:
            novo_back_off = snap_weight(back_peso * 1.05, config)
            if novo_back_off <= back_peso: novo_back_off = round(back_peso + incremento, 1)
        elif back_reps >= 7:
            novo_back_off = back_peso
        else:
            novo_back_off = snap_weight(back_peso * 0.95, config)
    else:
        novo_back_off = snap_weight(novo_top_set * 0.77, config)

    prep_a = snap_weight(novo_top_set * 0.45, config)
    prep_b = snap_weight(novo_top_set * 0.70, config)
    
    return {
        "Top_Set": novo_top_set,
        "Back_Off": novo_back_off,
        "Prep_A": prep_a,
        "Prep_B": prep_b,
        "Motivo": motivo
    }

# ==========================================
# 4. INTEGRAÇÃO COM HEVY API E TELEGRAM
# ==========================================
def atualizar_rotina_no_hevy(routine_id, nome_rotina, dicionario_novas_cargas):
    url = f"{HEVY_API_URL_ROUTINES}/{routine_id}"
    res_get = requests.get(url, headers=HEADERS_API)
    
    if res_get.status_code != 200: return False
        
    routine_data = res_get.json()
    routine_obj = routine_data.get("routine", routine_data)
    
    # Faxina na rotina
    routine_obj.pop("id", None)
    routine_obj.pop("folder_id", None)
    routine_obj.pop("updated_at", None)
    routine_obj.pop("created_at", None)
    
    atualizou_algo = False
    
    for ex in routine_obj.get("exercises", []):
        title = ex.get("title", "").strip()
        ex.pop("index", None)
        ex.pop("title", None)
        
        precisa_atualizar = title in dicionario_novas_cargas
        
        if precisa_atualizar:
            cargas = dicionario_novas_cargas[title]
            atualizou_algo = True
            w_count, n_count = 0, 0
            
        for s in ex.get("sets", []):
            s.pop("index", None)
            
            if precisa_atualizar:
                if s["type"] == "warmup":
                    if w_count == 0: s["weight_kg"] = cargas["Prep_A"]
                    elif w_count == 1: s["weight_kg"] = cargas["Prep_B"]
                    w_count += 1
                elif s["type"] == "normal":
                    if n_count == 0: s["weight_kg"] = cargas["Top_Set"]
                    elif n_count == 1: s["weight_kg"] = cargas["Back_Off"]
                    n_count += 1

    if atualizou_algo:
        res_put = requests.put(url, headers=HEADERS_API, json=routine_data)
        return res_put.status_code == 200
    return False

def montar_mensagem_telegram(fichas_atualizadas, recomendacoes):
    linhas = [
        "🏋️ <b>HEVY WEIGHT PIPELINE</b>",
        f"📅 {datetime.now().strftime('%d/%m/%Y')}",
        ""
    ]

    if fichas_atualizadas:
        linhas.append(f"⚙️ <b>{len(fichas_atualizadas)} Fichas Sincronizadas:</b> {', '.join(fichas_atualizadas)}")
    else:
        linhas.append("✅ Nenhuma ficha precisou de sincronização.")

    linhas.append("")
    linhas.append("📊 <b>Metas da Semana</b>")
    linhas.append("")

    for exercise_title, rec in recomendacoes.items():
        motivo = rec.get("Motivo", "")
        
        if "Meta batida" in motivo: status = "🔥"
        elif "Platô" in motivo: status = "⚠️"
        elif "Abaixo" in motivo: status = "🔄"
        else: status = "➡️"

        linhas.extend([
            f"{status} <b>{exercise_title}</b>",
            f"  Top: {formatar_peso(rec['Top_Set'])}kg | Back: {formatar_peso(rec['Back_Off'])}kg",
            f"  Warm: {formatar_peso(rec['Prep_A'])}kg → {formatar_peso(rec['Prep_B'])}kg",
            f"  <i>{motivo}</i>",
            ""
        ])

    return "\n".join(linhas)[:4000]

def enviar_notificacao_telegram(mensagem):
    """Envia uma mensagem formatada via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Telegram não configurado"

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        return False, response.text
    return True, "ok"

# ==========================================
# 5. MOTOR PRINCIPAL
# ==========================================
def main():
    data_limite = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print("--- 1. EXTRAINDO DADOS DA SEMANA ---")
    try:
        res = requests.get(f"{HEVY_API_URL_WORKOUTS}?since={data_limite}", headers=HEADERS_API, timeout=10)
        res.raise_for_status()
        dados = res.json()
        workouts = dados if isinstance(dados, list) else dados.get("workouts", [])
    except Exception as e:
        print(f"Erro na API do Hevy: {e}")
        return

    workouts.sort(key=lambda x: x.get("start_time", ""))
    estado_final_exercicios = {}

    for w in workouts:
        for ex in w.get("exercises", []):
            title = ex.get("title", "").strip()
            normal_sets = [s for s in ex.get("sets", []) if s["type"] == "normal"]
            
            if not normal_sets: continue
                
            top_peso = normal_sets[0].get("weight_kg")
            top_reps = normal_sets[0].get("reps")
            if top_peso is None or top_reps is None: continue
                
            back_peso, back_reps = None, None
            if len(normal_sets) > 1:
                back_peso = normal_sets[1].get("weight_kg")
                back_reps = normal_sets[1].get("reps")
            
            estado_final_exercicios[title] = processar_progressao(
                title, top_peso, top_reps, back_peso, back_reps
            )

    print("\n--- 2. SINCRONIZANDO COM AS ROTINAS DO HEVY ---")
    fichas_atualizadas = []
    for nome_rotina, r_id in ROTINAS_IDS.items():
        if "SEU-UUID-AQUI" not in r_id:
            sucesso = atualizar_rotina_no_hevy(r_id, nome_rotina, estado_final_exercicios)
            if sucesso: fichas_atualizadas.append(nome_rotina)
        else:
            print(f"⚠️ {nome_rotina} ignorada (UUID Placeholder detectado).")

    print("\n--- 3. ENVIANDO RELATÓRIO PARA O TELEGRAM ---")
    if estado_final_exercicios:
        mensagem = montar_mensagem_telegram(fichas_atualizadas, estado_final_exercicios)
        enviado, resposta = enviar_notificacao_telegram(mensagem)
        if enviado:
            print("✅ Notificação enviada com sucesso para o seu celular!")
        else:
            print(f"❌ Erro ao enviar Telegram: {resposta}")
    else:
        print("ℹ️ Nenhum exercício processado para enviar notificação.")

if __name__ == "__main__":
    main()