import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from config import HEVY_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# ==========================================
# CONFIGURAÇÕES DE TELEMETRIA E AUTENTICAÇÃO
# ==========================================
HEVY_API_URL = "https://api.hevyapp.com/v1/workouts"

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
def snap_weight(target_weight, config):
    """Aplica as restrições físicas do maquinário sobre a carga teórica."""
    eq_type = config["type"]
    tara = config["tara"]
    
    if eq_type == "plate_loaded":
        # Desconta a máquina, arredonda as anilhas para par (múltiplo de 5) e soma a máquina
        peso_anilhas = target_weight - tara
        if peso_anilhas <= 0: return tara
        return tara + (round(peso_anilhas / 5) * 5)
        
    elif eq_type == "cable":
        # Incrementos rígidos de 5 lbs (2.26796 kg)
        lb_factor = 2.26796
        return round(round(target_weight / lb_factor) * lb_factor, 1)
        
    elif eq_type == "dumbbell":
        # Halteres avançam de 2kg em 2kg por mão (Se total no app, avança de 4kg em 4kg)
        return round(target_weight / 4) * 4
        
    elif eq_type == "barbell":
        # Barras usam anilhas normais (Salto mínimo de 5kg total se anilhas de 2.5kg por lado)
        peso_anilhas = target_weight - tara
        if peso_anilhas <= 0: return tara
        return tara + (round(peso_anilhas / 5) * 5)
        
    elif eq_type == "machine_pin":
        # Máquinas normais de pino avançam de 2.5kg em 2.5kg ou 5kg
        return round(target_weight / 2.5) * 2.5
        
    return round(target_weight, 1)


def get_min_increment(config):
    """Retorna o menor incremento fisico disponivel para o tipo de equipamento."""
    eq_type = config["type"]
    if eq_type in {"plate_loaded", "barbell"}:
        return 5.0
    if eq_type == "dumbbell":
        return 4.0
    if eq_type == "cable":
        return 2.26796
    if eq_type == "machine_pin":
        return 2.5
    return 2.5


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
    config = EQUIPMENT_CONFIG.get(exercise_title, {"type": "standard", "tara": 0.0})
    
    # Cálculo de Estimação de 1RM (Fórmula de Epley)
    one_rm = np.float64(peso_atual) * (1 + (np.float64(reps_feitas) / 30.0))

    motivo = ""

    prep_a_pct = 0.45   # faixa 40-50%
    prep_b_pct = 0.70   # fixo 70%
    top_pct = 0.825     # faixa 80-85%
    backoff_pct = 0.625 # faixa 60-65%
    fator_deload = 1.0

    # Regra de segurança para hiato longo sem treino
    if dias_sem_treino > 10:
        top_pct = 0.80
        backoff_pct = 0.60
        prep_a_pct = 0.40
        fator_deload = 0.90
        motivo = "Destreino (>10 dias): usar banda inferior + deload de 10%"
    # Se houver plato (3 semanas iguais), nao forcamos progressao de carga
    elif plateau:
        top_pct = 0.80
        backoff_pct = 0.60
        motivo = "Plato detectado (3 semanas): banda inferior e sugerir variacao"
    
    # Motor de tomada de decisão baseado no teto de repetições (5-9 reps)
    elif reps_feitas >= 9:
        top_pct = 0.85
        backoff_pct = 0.65
        prep_a_pct = 0.50
        motivo = "Meta batida (>=9 reps): usar banda superior de intensidade"
    elif reps_feitas >= 5:
        top_pct = 0.825
        backoff_pct = 0.625
        prep_a_pct = 0.45
        motivo = "Faixa alvo parcial (5-8 reps): manter banda intermediaria"
    else:
        top_pct = 0.80
        backoff_pct = 0.60
        prep_a_pct = 0.40
        fator_deload = 0.90
        motivo = "Abaixo da faixa (<5 reps): banda inferior + deload de 10%"

    # Todas as series sao derivadas do 1RM estimado
    prep_a = snap_weight(float(one_rm) * prep_a_pct * fator_deload, config)
    prep_b = snap_weight(float(one_rm) * prep_b_pct * fator_deload, config)
    novo_top_set = snap_weight(float(one_rm) * top_pct * fator_deload, config)
    novo_back_off = snap_weight(float(one_rm) * backoff_pct * fator_deload, config)
    
    return {
        "1RM_Est": float(np.round(one_rm, 1)),
        "Prep_A": prep_a,
        "Prep_B": prep_b,
        "Top_Set": novo_top_set,
        "Back_Off": novo_back_off,
        "Motivo": motivo,
        "Perc_Prep_A": prep_a_pct,
        "Perc_Prep_B": prep_b_pct,
        "Perc_Top": top_pct,
        "Perc_Back_Off": backoff_pct,
        "Fator_Deload": fator_deload,
    }


def extrair_workouts(payload):
    """Normaliza diferentes formatos de resposta da Hevy para uma lista de workouts."""
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    # Endpoint de workouts paginados
    if isinstance(payload.get("workouts"), list):
        return payload["workouts"]

    # Event payload (ex.: UpdatedWorkout)
    workout_unico = payload.get("workout")
    if isinstance(workout_unico, dict):
        return [workout_unico]

    return []


def get_latest_workout(workouts):
    """Retorna o workout mais recente baseado no start_time."""
    if not workouts:
        return None

    def sort_key(workout):
        dt = parse_iso_datetime(workout.get("start_time"))
        return dt or datetime(1970, 1, 1, tzinfo=timezone.utc)

    return sorted(workouts, key=sort_key, reverse=True)[0]


def fetch_workout_by_id(workout_id, headers):
    """Busca o treino completo por ID para garantir payload valido no PUT."""
    response = requests.get(f"{HEVY_API_URL}/{workout_id}", headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()


def compact_dict(data):
    """Remove chaves com valor None ou string vazia de um dicionario."""
    cleaned = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        cleaned[k] = v
    return cleaned


def formatar_peso(valor):
    """Formata pesos sem sufixo decimal desnecessario."""
    if isinstance(valor, (int, np.integer)):
        return str(int(valor))

    if isinstance(valor, float):
        if valor.is_integer():
            return str(int(valor))
        return f"{valor:.1f}".rstrip("0").rstrip(".")

    return str(valor)


def build_put_workout_payload(workout):
    """Constrói payload de update preservando os campos relevantes do treino."""
    payload = compact_dict({
        "title": workout.get("title"),
        "description": workout.get("description"),
        "routine_id": workout.get("routine_id"),
        "start_time": workout.get("start_time"),
        "end_time": workout.get("end_time"),
        "exercises": [],
    })
    if "exercises" not in payload:
        payload["exercises"] = []

    for exercise in workout.get("exercises", []):
        ex_payload = compact_dict({
            "exercise_template_id": exercise.get("exercise_template_id"),
            "sets": [],
        })
        if "sets" not in ex_payload:
            ex_payload["sets"] = []

        for set_item in exercise.get("sets", []):
            ex_payload["sets"].append(
                compact_dict(
                    {
                        "type": set_item.get("type"),
                        "weight_kg": set_item.get("weight_kg"),
                        "reps": set_item.get("reps"),
                        "distance_meters": set_item.get("distance_meters"),
                        "duration_seconds": set_item.get("duration_seconds"),
                        "rpe": set_item.get("rpe"),
                        "custom_metric": set_item.get("custom_metric"),
                    }
                )
            )

        payload["exercises"].append(ex_payload)

    return payload


def aplicar_recomendacoes_no_workout(workout, recomendacoes):
    """Aplica Top Set e Back-Off no treino mais recente de forma conservadora."""
    atualizado = build_put_workout_payload(workout)
    alteracoes = 0

    for exercise in atualizado.get("exercises", []):
        title = exercise.get("title")
        rec = recomendacoes.get(title)
        if not rec:
            continue

        normal_sets = [s for s in exercise.get("sets", []) if s.get("type") == "normal"]
        normal_sets = sorted(normal_sets, key=lambda s: s.get("index", 10**9))

        if len(normal_sets) >= 1:
            if normal_sets[0].get("weight_kg") != rec["Top_Set"]:
                normal_sets[0]["weight_kg"] = rec["Top_Set"]
                alteracoes += 1

        if len(normal_sets) >= 2:
            if normal_sets[1].get("weight_kg") != rec["Back_Off"]:
                normal_sets[1]["weight_kg"] = rec["Back_Off"]
                alteracoes += 1

    return atualizado, alteracoes


def atualizar_workout(workout_id, payload, headers):
    """Envia update do workout para API da Hevy."""
    request_body = {"workout": payload}
    response = requests.put(
        f"{HEVY_API_URL}/{workout_id}",
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


def montar_mensagem_telegram(workout, alteracoes, recomendacoes):
    """Monta um resumo compacto das cargas calculadas para envio ao Telegram."""
    linhas = []
    titulo = workout.get("title") or "Workout sem titulo"
    data_inicio = (workout.get("start_time") or "")[:10] or "sem data"
    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas.append(f"[{agora_str}] Hevy Weight Adjust")
    linhas.append(f"Hevy atualizado: {titulo} ({data_inicio})")
    linhas.append(f"Alterações aplicadas: {alteracoes}")
    if alteracoes == 0:
        linhas.append("Nenhuma carga precisou ser alterada neste run.")

    for exercise_title in sorted(recomendacoes.keys()):
        rec = recomendacoes[exercise_title]
        linhas.append(
            f"- {exercise_title}: Top {formatar_peso(rec['Top_Set'])} kg | Back-Off {formatar_peso(rec['Back_Off'])} kg | Prep A {formatar_peso(rec['Prep_A'])} kg | Prep B {formatar_peso(rec['Prep_B'])} kg"
        )

    mensagem = "\n".join(linhas)
    return mensagem[:3900]


def enviar_notificacao_telegram(mensagem):
    """Envia uma mensagem simples via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Telegram nao configurado"

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
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
        response = requests.get(f"{HEVY_API_URL}?since={data_limite}", headers=headers, timeout=10)
        response.raise_for_status()
        workouts = extrair_workouts(response.json())
    except Exception as e:
        print(f"Erro ao conectar com a API do Hevy: {e}")
        return

    if not workouts:
        print("Nenhum workout encontrado no período informado.")
        return

    print(f"--- RELATÓRIO DE PROGRESSÃO AUTOMÁTICA EM COMPILAÇÃO ---")

    # Constrói uma base historica por exercicio usando pandas
    historico = []
    for w in workouts:
        inicio_dt = parse_iso_datetime(w.get("start_time"))
        for ex in w.get("exercises", []):
            title = ex.get("title") or "(sem nome)"
            top_set_efetuado = get_top_set_normal(ex)
            if not top_set_efetuado:
                continue

            peso = top_set_efetuado.get("weight_kg")
            reps = top_set_efetuado.get("reps")
            if peso is None or reps is None:
                continue

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

    # Uma recomendacao por exercicio baseada no treino mais recente dele
    recomendacoes = {}
    for exercise_title, grupo in df_hist.groupby("exercise_title", sort=True):
        grupo = grupo.reset_index(drop=True)
        atual = grupo.iloc[0]
        peso = float(atual["peso"])
        reps = int(atual["reps"])
        data_ultimo = atual["workout_start"]

        if pd.isna(data_ultimo):
            dias_sem_treino = 999
        else:
            dias_sem_treino = (agora - data_ultimo).days

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
        if plateau:
            print("  ↳ ALERTA: Platô por 3 semanas. Sugestão: trocar por variação análoga.")
        print("  ↳ Próximo Alvo:")
        print(f"    - Prep A (10-12 reps): {cargas['Prep_A']} kg")
        print(f"    - Prep B (3-4 reps):   {cargas['Prep_B']} kg")
        print(f"    - Top Set (5-9 reps):  {cargas['Top_Set']} kg")
        print(f"    - Back-Off (7-10 reps):{cargas['Back_Off']} kg")

    # Atualiza automaticamente o treino mais recente a cada execução
    workout_alvo = get_latest_workout(workouts)
    if not workout_alvo or not workout_alvo.get("id"):
        print("\nNenhum workout alvo valido para atualizar na API.")
        return

    try:
        workout_completo = fetch_workout_by_id(workout_alvo["id"], headers)
    except Exception as e:
        print(f"\nFalha ao buscar workout completo antes do update: {e}")
        return

    payload_update, alteracoes = aplicar_recomendacoes_no_workout(workout_completo, recomendacoes)
    try:
        if alteracoes > 0:
            atualizar_workout(workout_alvo["id"], payload_update, headers)
            print(f"\nWorkout atualizado na Hevy com sucesso. Alterações aplicadas: {alteracoes}")
            print(f"Workout ID atualizado: {workout_alvo['id']}")
        else:
            print("\nNenhuma carga precisou ser alterada no workout mais recente.")

        mensagem = montar_mensagem_telegram(workout_alvo, alteracoes, recomendacoes)
        sucesso_telegram, detalhe_telegram = enviar_notificacao_telegram(mensagem)
        if sucesso_telegram:
            print("Notificacao Telegram enviada com sucesso.")
        else:
            print(f"Falha ao enviar notificacao no Telegram: {detalhe_telegram}")
    except Exception as e:
        print(f"\nFalha ao atualizar workout na Hevy: {e}")

if __name__ == "__main__":
    main()