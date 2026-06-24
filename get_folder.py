import requests
from config import HEVY_API_KEY

HEADERS = {"Accept": "application/json", "api-key": HEVY_API_KEY}

def listar_pastas_das_fichas():
    url_routines = "https://api.hevyapp.com/v1/routines"
    
    print("Buscando fichas na API...\n")
    
    res = requests.get(url_routines, headers=HEADERS)
    if res.status_code != 200:
        print(f"Erro: {res.text}")
        return
        
    dados = res.json()
    rotinas = dados if isinstance(dados, list) else dados.get("routines", [])
    
    for r in rotinas:
        titulo = r.get("title", "Sem título")
        folder_id = r.get("folder_id")
        
        # Se não tiver pasta, mostramos como "Nenhuma/Raiz"
        folder_display = folder_id if folder_id else "Nenhuma/Raiz"
        
        print(f"{titulo} - {folder_display}")

if __name__ == "__main__":
    listar_pastas_das_fichas()