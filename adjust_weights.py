import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from config import HEVY_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# ==========================================
# CONFIGURAÇÕES DE TELEMETRIA E AUTENTICAÇÃO
# ==========================================
HEVY_WORKOUTS_URL = "https://api.hevyapp.com/v1/workouts"
HEVY_ROUTINES_URL = "https://api.hevyapp.com/v1/routines"

# IDs das Fichas (Templates de Treino)
FICHAS_IDS = [
    "9e1f1270-c1c2-4e17-b106-ef629da9fcf9", # Sabado - Pernas Completas
    "df62efd0-d1ed-4321-ae8d-0aeb8eb49237", # Sexta - Costas e Peito
    "e9c0a23e-6b8d-4507-9c28-dba043540e91", # Quinta - Ombros e Braços
    "e5729a7d-2ece-4d1e-8e58-e10239b8f093", # Terça - Peito e Costas
    "a5013e79-cb4e-4872-9882-5e147c756d27"  # Segunda: Ombros e Braços
]

# Dicionário de configuração de Hardware (Taras e Regras de Snapping da SmartFit)
EQUIPMENT_CONFIG = {
    # Máquinas Articuladas (Salto mínimo de 5kg total devido a anilhas de 2.5kg por lado)
    "Press De Peito Iso-Lateral (Máquina)": {"type": "plate_loaded", "tara": 13.5},
    "Remadas Iso-Lateral (Máquina)": {"type": "plate_loaded", "tara": 22.6},
    "Leg Press 45° (Máquina)": {"type": "plate_loaded", "tara": 75.0},
    "Elevação Unilateral de Panturrilha em Pé (Máquina)": {"type": "plate_loaded", "tara": 30.4},
    
    # Polias (Salto fixo de 5 lbs = ~2.268 kg por placa)
    "Elevação Lateral Unilateral (Cabo)": {"type": "cable", "tara": 0.0},
    "Rosca Direta Polia Baixa": {"type": "cable", "tara": 0.0},
    "Tríceps Francês na Polia": {"type": "cable", "tara": 0.0},
    "Tríceps Pushdown (Corda)": {"type": "cable", "tara": 0.0},
    "Puxada Com Braços Esticados (Corda)": {"type": "cable", "tara": 0.0},
    "Puxada Alta - Pegada Triângulo": {"type": "cable", "tara": 0.0},
    "Face Pull": {"type": "cable", "tara": 0.0},
    
    # Halteres e Barras Livres (Salto de 2kg por halter / 5kg por barra)
    "Incline Bench Press (Halteres)": {"type": "dumbbell", "tara": 0.0},
    "Elevação Lateral com Halteres": {"type": "dumbbell", "tara": 0.0},
    "Rosca Martelo Alternada": {"type": "dumbbell", "tara": 0.0},
    "Levantamento Terra Romeno (Barbell)": {"type": "barbell", "tara": 20.0},
    
    # Máquinas Seletorizadas por Pinos Padrão (Salto de 2.5kg ou 5kg)
    "Crucifixo no Voador (Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Aberturas Invertidas De Ombro Posterior (Na Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Cadeira Extensora (Máquina)": {"type": "machine_pin", "tara": 0.0},
    "Cadeira Flexora (Máquina)": {"type": "machine_pin", "tara": 0.0},
}

# ==========================================
# FUNÇÕES DE ARREDONDAMENTO (SNAPPING)
# ==========================================

def get_equipment_config(title):
    """Busca a configuração do equipamento de forma case-insensitive com fallback inteligente."""
    title_lower = title.lower()
    
    for config_name, config_data in EQUIPMENT_CONFIG.items():
        if config_name.lower() == title_lower:
            return config_data
            
    if any(kw in title_lower for kw in ["cabo", "polia", "corda", "triângulo", "triangulo", "pushdown", "francês", "frances"]):
        return {"type": "cable", "tara": 0.0}
    if any(kw in title_lower for kw in ["halter", "dumbbell", "alternada", "martelo"]):
        return {"type": "dumbbell", "tara": 0.0}
    if any(kw in title_lower for kw in ["barra", "barbell", "romeno"]):
        return {"type": "barbell", "tara": 20.0}
    if any(kw in title_lower for kw in ["máquina", "maquina", "voador", "seletorizada", "pino"]):
        return {"type": "machine_pin", "tara": 0.0}
        
    return {"type": "standard", "tara": 0.0}

def snap_weight(target_weight, config):
    """Aplica as restrições físicas do maquinário sobre a carga teórica."""
    eq_type = config["type"]
    tara = config["tara"]
    
    if eq_type == "plate_loaded":
        peso_anilhas = target_weight - tara
        if peso_anilhas <= 0: return tara
        return tara + (round(peso_anilhas / 5) * 5)
        
    elif eq_type == "cable":
        lb_factor = 2.26796
        return round(round(target_weight / lb_factor) * lb_factor, 1)
        
    elif eq_type == "dumbbell":
        return round(target_weight / 4) * 4
        
    elif eq_type == "barbell":
        peso_anilhas = target_weight - tara
        if peso_anilhas <= 0: return tara
        return tara + (round(peso_anilhas / 5) * 5)
        
    elif eq_type == "machine_pin":
        return round(target_weight / 2.5) * 2.5
        
    return round(target_weight, 1)

def parse_iso_datetime(value):
    """Converte timestamp ISO8601 para datetime UTC de forma tolerante."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def get_top_set_normal(exercise):
    """Seleciona o Top Set como o set 'normal' de menor indice."""
    normal_sets = [s for s in exercise.get("sets", []) if s.get("type") == "normal"]
    if not normal_sets:
        return None
    return sorted(normal_sets, key=lambda s: s.get("index", 10**9))[0]

# ==========================================
# CÁLCULOS METODOLÓGICOS (DOUBLE PROGRESSION)
# ==========================================
def processar_progressao(exercise_title, peso_atual, reps_feitas, dias_sem_treino, plateau):
    """Aplica as regras biológicas do Top Set e calcula o Back-Off."""
    config = get_equipment_config(exercise_title)
    
    one_rm = np.float64(peso_atual) * (1 + (np.float64(reps_feitas) / 30.0))
    motivo = ""

    if dias_sem_treino > 10:
        peso_teorico_top = peso_atual * 0.90
        motivo = "Destreino (>10 dias): Deload preventivo de 10%"
    elif plateau:
        peso_teorico_top = peso_atual * 0.95
        motivo = "Platô detectado (3 semanas): Quebra de carga (Deload 5%)"
    elif reps_feitas >= 9:
        peso_teorico_top = peso_atual * 1.05
        motivo = "Meta batida (>=9 reps): Aumento de carga (~5%)"
    elif reps_feitas >= 5:
        peso_teorico_top = peso_atual
        motivo = "Faixa alvo parcial (5-8 reps): Manter carga e progredir reps"
    else:
        peso_teorico_top = peso_atual * 0.90
        motivo = "Abaixo da faixa (<5 reps): Deload técnico de 10%"

    novo_top_set = snap_weight(peso_teorico_top, config)
    novo_back_off = snap_weight(novo_top_set * 0.77, config)
    prep_a = snap_weight(novo_top_set * 0.45, config)
    prep_b = snap_weight(novo_top_set * 0.70, config)
    
    return {
        "1RM_Est": float(np.round(one_rm, 1)),
        "Prep_A": prep_a,
        "Prep_B": prep_b,
        "Top_Set": novo_top_set,
        "Back_Off": novo_back_off,
        "Motivo": motivo
    }

def extrair_workouts(payload):
    """Normaliza diferentes formatos de resposta da Hevy para uma lista de workouts."""
    if isinstance(payload, list): return payload
    if not isinstance(payload, dict): return []
    if isinstance(payload.get("workouts"), list): return payload["workouts"]
    workout_unico = payload.get("workout")
    if isinstance(workout_unico, dict): return [workout_unico]
    return []

def get_latest_workout(workouts):
    """Retorna o workout mais recente baseado no start_time (usado p/ relatório Telegram)."""
    if not workouts:
        return None
    def sort_key(workout):
        dt = parse_iso_datetime(workout.get("start_time"))
        return dt or datetime(1970, 1, 1, tzinfo=timezone.utc)
    return sorted(workouts, key=sort_key, reverse=True)[0]

def compact_dict(data):
    """Remove chaves com valor None ou string vazia de um dicionario."""
    cleaned = {}
    for k, v in data.items():
        if v is None: continue
        if isinstance(v, str) and v.strip() == "": continue
        cleaned[k] = v
    return cleaned

def formatar_peso(valor):
    """Formata pesos sem sufixo decimal desnecessario."""
    if isinstance(valor, (int, np.integer)): return str(int(valor))
    if isinstance(valor, float):
        if valor.is_integer(): return str(int(valor))
        return f"{valor:.1f}".rstrip("0").rstrip(".")
    return str(valor)

# ==========================================
# FUNÇÕES DE MANIPULAÇÃO DE FICHAS (ROUTINES)
# ==========================================
def fetch_routine_by_id(routine_id, headers):
    """Busca a ficha completa por ID para garantir payload valido no PUT."""
    response = requests.get(f"{HEVY_ROUTINES_URL}/{routine_id}", headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()

def build_put_routine_payload(routine):
    """Constrói payload enxuto para a Ficha, preservando as notas e supersets."""
    payload = compact_dict({
        "title": routine.get("title"),
        "notes": routine.get("notes"),
        # A linha "folder_id": routine.get("folder_id"), foi removida daqui!
        "exercises": [],
    })
    
    for exercise in routine.get("exercises", []):
        ex_payload = compact_dict({
            "exercise_template_id": exercise.get("exercise_template_id"),
            "superset_id": exercise.get("superset_id"), 
            "notes": exercise.get("notes"),
            "sets": [],
        })
        
        for set_item in exercise.get("sets", []):
            ex_payload["sets"].append(
                compact_dict({
                    "type": set_item.get("type"),
                    "weight_kg": set_item.get("weight_kg"),
                    "reps": set_item.get("reps"),
                    "distance_meters": set_item.get("distance_meters"),
                    "duration_seconds": set_item.get("duration_seconds"),
                    "rpe": set_item.get("rpe")
                })
            )
        payload["exercises"].append(ex_payload)
    return payload

def aplicar_recomendacoes_na_rotina(routine_original, recomendacoes):
    """Aplica as recomendações nas fichas baseando-se no dicionário original."""
    atualizado = build_put_routine_payload(routine_original)
    alteracoes = 0

    # Iteramos paralelamente: lemos o título do dicionário original, mas editamos o payload atualizado
    for orig_ex, update_ex in zip(routine_original.get("exercises", []), atualizado.get("exercises", [])):
        title = orig_ex.get("title")
        
        if not title:
            continue
            
        rec = recomendacoes.get(title)
        if not rec:
            continue

        normal_sets = [s for s in update_ex.get("sets", []) if s.get("type") == "normal"]
        
        # Como o payload enxuto não tem "index", garantimos a ordem da lista
        if len(normal_sets) >= 1 and normal_sets[0].get("weight_kg") != rec["Top_Set"]:
            normal_sets[0]["weight_kg"] = rec["Top_Set"]
            alteracoes += 1

        if len(normal_sets) >= 2 and normal_sets[1].get("weight_kg") != rec["Back_Off"]:
            normal_sets[1]["weight_kg"] = rec["Back_Off"]
            alteracoes += 1

    return atualizado, alteracoes

def atualizar_routine(routine_id, payload, headers):
    """Envia update da ficha para API da Hevy."""
    request_body = {"routine": payload}
    response = requests.put(
        f"{HEVY_ROUTINES_URL}/{routine_id}",
        headers={**headers, "Content-Type": "application/json"},
        json=request_body,
        timeout=20,
    )
    if response.status_code >= 400:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text}",
            response=response,
        )
    return response.json() if response.text else {}

# ==========================================
# NOTIFICAÇÕES (TELEGRAM)
# ==========================================
def montar_mensagem_telegram(workout_recente, total_alteracoes, recomendacoes):
    titulo = workout_recente.get("title") or "Último Treino Analisado"
    data_inicio = (workout_recente.get("start_time") or "")[:10]

    try:
        dt = datetime.fromisoformat(data_inicio.replace("Z", "+00:00"))
        data_formatada = dt.strftime("%d/%m/%Y")
    except Exception:
        data_formatada = data_inicio or "Sem data"

    linhas = [
        "🏋️ <b>HEVY WEIGHT PIPELINE</b>",
        f"Último log: <i>{titulo}</i> ({data_formatada})",
        ""
    ]

    if total_alteracoes > 0:
        linhas.append(f"⚙️ <b>{total_alteracoes} ajustes</b> aplicados em suas Fichas!")
    else:
        linhas.append("✅ Nenhum ajuste necessário nas Fichas.")

    linhas.append("")
    linhas.append("📊 <b>Status dos Exercícios (Último Treino):</b>")
    linhas.append("")

    exercicios = [
        ex.get("title")
        for ex in workout_recente.get("exercises", [])
        if ex.get("title")
    ]

    for exercise_title in exercicios:
        rec = recomendacoes.get(exercise_title)
        if not rec:
            continue

        motivo = rec.get("Motivo", "")
        if "Meta batida" in motivo: status = "🔥"
        elif "Platô" in motivo or "Plato" in motivo: status = "⚠️"
        elif "Destreino" in motivo: status = "📉"
        elif "Abaixo da faixa" in motivo: status = "🔄"
        else: status = "➡️"

        linhas.extend([
            f"{status} <b>{exercise_title}</b>",
            (
                f"Top {formatar_peso(rec['Top_Set'])}kg | "
                f"Back {formatar_peso(rec['Back_Off'])}kg | "
                f"Warm {formatar_peso(rec['Prep_A'])}kg→{formatar_peso(rec['Prep_B'])}kg"
            ),
            f"<i>{motivo}</i>",
            ""
        ])

    return "\n".join(linhas)[:4000]

def enviar_notificacao_telegram(mensagem):
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
# MOTOR PRINCIPAL DE EXECUÇÃO
# ==========================================
def main():
    headers = {"Accept": "application/json", "api-key": HEVY_API_KEY}
    
    # Janela de 35 dias para suportar regra de plato (3 semanas) e hiatos >10 dias
    data_limite = (datetime.utcnow() - timedelta(days=35)).isoformat() + "Z"
    
    try:
        # Puxamos o histórico de WORKOUTS (treinos passados) para calcular a progressão
        response = requests.get(f"{HEVY_WORKOUTS_URL}?since={data_limite}", headers=headers, timeout=10)
        response.raise_for_status()
        workouts = extrair_workouts(response.json())
    except Exception as e:
        print(f"Erro ao conectar com a API do Hevy: {e}")
        return

    if not workouts:
        print("Nenhum workout encontrado no período informado.")
        return

    print(f"--- RELATÓRIO DE PROGRESSÃO AUTOMÁTICA EM COMPILAÇÃO ---")

    historico = []
    for w in workouts:
        inicio_dt = parse_iso_datetime(w.get("start_time"))
        for ex in w.get("exercises", []):
            title = ex.get("title") or "(sem nome)"
            top_set_efetuado = get_top_set_normal(ex)
            if not top_set_efetuado: continue

            peso = top_set_efetuado.get("weight_kg")
            reps = top_set_efetuado.get("reps")
            if peso is None or reps is None: continue

            historico.append(
                {
                    "exercise_title": title,
                    "workout_start": inicio_dt,
                    "peso": float(peso),
                    "reps": int(reps),
                    "one_rm_est": float(np.round(float(peso) * (1 + (float(reps) / 30.0)), 1)),
                }
            )

    if not historico:
        print("Nenhum top set valido encontrado para calcular progressao.")
        return

    df_hist = pd.DataFrame(historico)
    df_hist = df_hist.sort_values(["exercise_title", "workout_start"], ascending=[True, False])
    agora = datetime.utcnow().astimezone()

    recomendacoes = {}
    for exercise_title, grupo in df_hist.groupby("exercise_title", sort=True):
        grupo = grupo.reset_index(drop=True)
        atual = grupo.iloc[0]
        peso = float(atual["peso"])
        reps = int(atual["reps"])
        data_ultimo = atual["workout_start"]

        if pd.isna(data_ultimo): dias_sem_treino = 999
        else: dias_sem_treino = (agora - data_ultimo).days

        plateau = False
        if len(grupo) >= 3:
            ultimos_3 = grupo.iloc[:3]
            plateau = (ultimos_3["peso"].nunique() == 1) and (ultimos_3["reps"].nunique() == 1)

        cargas = processar_progressao(
            exercise_title=exercise_title,
            peso_atual=peso,
            reps_feitas=reps,
            dias_sem_treino=dias_sem_treino,
            plateau=plateau,
        )
        recomendacoes[exercise_title] = cargas

        print(f"\nExercício: {exercise_title}")
        print("-" * 50)
        print(f"  ↳ Último Top Set: {peso} kg x {reps} reps")
        print(f"  ↳ 1RM Est (Epley): {cargas['1RM_Est']} kg")
        print(f"  ↳ Dias sem treino: {dias_sem_treino}")
        print(f"  ↳ Regra aplicada: {cargas['Motivo']}")
        if plateau: print("  ↳ ALERTA: Platô por 3 semanas. Sugestão: trocar por variação análoga.")
        print("  ↳ Próximo Alvo:")
        print(f"    - Prep A (10-12 reps): {cargas['Prep_A']} kg")
        print(f"    - Prep B (3-4 reps):   {cargas['Prep_B']} kg")
        print(f"    - Top Set (5-9 reps):  {cargas['Top_Set']} kg")
        print(f"    - Back-Off (7-10 reps):{cargas['Back_Off']} kg")

    print("\n--- APLICANDO CARGAS NAS FICHAS FUTURAS (ROUTINES) ---")
    total_alteracoes = 0
    
    for rotina_id in FICHAS_IDS:
        try:
            rotina_completa = fetch_routine_by_id(rotina_id, headers)
            dados_rotina = rotina_completa.get("routine", rotina_completa)
            
            payload_update, alteracoes = aplicar_recomendacoes_na_rotina(dados_rotina, recomendacoes)
            
            if alteracoes > 0:
                atualizar_routine(rotina_id, payload_update, headers)
                nome_ficha = dados_rotina.get('title', rotina_id)
                print(f"✅ Ficha '{nome_ficha}' atualizada com sucesso! {alteracoes} ajustes.")
                total_alteracoes += alteracoes
            else:
                nome_ficha = dados_rotina.get('title', rotina_id)
                print(f"➡️ Ficha '{nome_ficha}' verificada. Não precisou de ajustes.")
                
        except Exception as e:
            print(f"❌ Falha ao processar e atualizar a ficha {rotina_id}: {e}")

    try:
        workout_alvo = get_latest_workout(workouts)
        if workout_alvo:
            mensagem = montar_mensagem_telegram(workout_alvo, total_alteracoes, recomendacoes)
            sucesso_telegram, detalhe_telegram = enviar_notificacao_telegram(mensagem)
            if sucesso_telegram:
                print("\nNotificacao Telegram enviada com sucesso.")
            else:
                print(f"\nFalha ao enviar notificacao no Telegram: {detalhe_telegram}")
    except Exception as e:
        print(f"\nFalha ao preparar mensagem do Telegram: {e}")

if __name__ == "__main__":
    main()