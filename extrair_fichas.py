import requests
from config import HEVY_API_KEY

# ==========================================
# CONFIGURAÇÕES
# ==========================================
HEVY_API_URL_ROUTINES = "https://api.hevyapp.com/v1/routines"
HEADERS = {"Accept": "application/json", "api-key": HEVY_API_KEY}

def formatar_peso(peso):
    """Remove o .0 de pesos inteiros para o Markdown ficar mais limpo."""
    if peso is None: 
        return "-"
    return str(peso).replace('.0', '') if isinstance(peso, float) and peso.is_integer() else str(peso)

def traduzir_tipo_serie(set_type):
    """Traduz e associa um emoji ao tipo de série."""
    tipos = {
        "normal": ("🔥", "Normal"),
        "warmup": ("💨", "Aquecimento"),
        "failure": ("🩸", "Falha"),
        "drop_set": ("📉", "Drop Set")
    }
    return tipos.get(set_type, ("➡️", set_type.capitalize()))

def main():
    print("🔄 Conectando à nuvem do Hevy e baixando rotinas...")
    try:
        res = requests.get(HEVY_API_URL_ROUTINES, headers=HEADERS)
        res.raise_for_status()
        dados = res.json()
        rotinas = dados if isinstance(dados, list) else dados.get("routines", [])
    except Exception as e:
        print(f"❌ Erro ao acessar a API: {e}")
        return

    if not rotinas:
        print("⚠️ Nenhuma rotina encontrada na sua conta.")
        return

    # ==========================================
    # AGRUPAMENTO POR PASTA
    # ==========================================
    pastas = {}
    for r in rotinas:
        # Se por acaso tiver alguma ficha solta sem pasta, agrupa como "Sem Pasta"
        folder_id = r.get("folder_id") or "Sem Pasta" 
        
        if folder_id not in pastas:
            pastas[folder_id] = []
        pastas[folder_id].append(r)

    # ==========================================
    # MENU INTERATIVO
    # ==========================================
    print("\n📂 PASTAS DE TREINO ENCONTRADAS:")
    print("=" * 70)
    
    opcoes_menu = []
    
    for indice, (folder_id, lista_fichas) in enumerate(pastas.items(), 1):
        opcoes_menu.append(lista_fichas) # Guarda a lista de fichas na opção correspondente
        
        # Pega o nome de todas as fichas para mostrar no preview
        nomes_fichas = [f.get("title", "Sem título") for f in lista_fichas]
        
        print(f"[{indice}] Pasta ID: {folder_id}")
        print(f"    ↳ Fichas ({len(lista_fichas)}): {', '.join(nomes_fichas)}")
        print("-" * 70)

    # Opção extra para juntar tudo
    indice_todas = len(opcoes_menu) + 1
    print(f"[{indice_todas}] 🌟 Extrair TUDO (Juntar todas as pastas em um único arquivo)")
    print("=" * 70)

    # Coleta a escolha do usuário
    while True:
        escolha = input(f"\n👉 Digite o número da pasta que deseja extrair (1 a {indice_todas}): ")
        if escolha.isdigit():
            escolha = int(escolha)
            if 1 <= escolha <= len(opcoes_menu):
                rotinas_selecionadas = opcoes_menu[escolha - 1]
                break
            elif escolha == indice_todas:
                rotinas_selecionadas = rotinas
                break
        print("❌ Opção inválida. Digite apenas o número.")

    # Ordena as rotinas da pasta escolhida em ordem alfabética para o Markdown
    rotinas_selecionadas.sort(key=lambda x: x.get('title', ''))

    print(f"\n⚙️ Gerando Markdown para {len(rotinas_selecionadas)} treinos selecionados...")

    # ==========================================
    # GERAÇÃO DO MARKDOWN
    # ==========================================
    linhas_md = [
        "# 🏋️ Meus Treinos (Hevy)",
        "> *Documento gerado automaticamente com as rotinas extraídas diretamente do aplicativo.*",
        "",
        "---",
        ""
    ]

    for rotina in rotinas_selecionadas:
        titulo_rotina = rotina.get("title", "Treino Sem Nome")
        linhas_md.append(f"## 📋 {titulo_rotina}\n")
        
        exercicios = rotina.get("exercises", [])
        if not exercicios:
            linhas_md.append("*Nenhum exercício cadastrado nesta ficha.*\n")
            continue

        for i, ex in enumerate(exercicios, 1):
            titulo_ex = ex.get("title", "Exercício Desconhecido")
            
            # Garantia de que notas vazias não quebram o código
            anotacoes = (ex.get("notes") or "").strip()
            
            linhas_md.append(f"### {i}. {titulo_ex}")
            
            if anotacoes:
                linhas_md.append(f"*📝 {anotacoes}*")
            
            linhas_md.append("\n| Série | Tipo | Peso (kg) | Reps |")
            linhas_md.append("|:---:|:---|:---:|:---:|")
            
            for j, s in enumerate(ex.get("sets", []), 1):
                emoji, tipo_texto = traduzir_tipo_serie(s.get("type", "normal"))
                peso = formatar_peso(s.get("weight_kg"))
                
                # Garantia de que reps vazias viram traços e não 'None'
                reps_brutas = s.get("reps")
                reps = "-" if reps_brutas is None else reps_brutas
                
                linhas_md.append(f"| {j} | {emoji} {tipo_texto} | **{peso}** | {reps} |")
            
            linhas_md.append("\n") 
        
        linhas_md.append("---\n")

    nome_arquivo = "Treinos.md"
    try:
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas_md))
        print(f"✅ Arquivo '{nome_arquivo}' gerado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao salvar o arquivo: {e}")

if __name__ == "__main__":
    main()