import requests
import pandas as pd
import sqlite3
from datetime import datetime
import os

# Tenta importar a chave do config, senão avisa o usuário
try:
    from config import HEVY_API_KEY
except ImportError:
    HEVY_API_KEY = None

BASE_URL = "https://api.hevyapp.com"

class HevyPipeline:
    def __init__(self, db_name="hevy_analytics.db"):
        self.db_name = db_name
        self.headers = {
            "api-key": HEVY_API_KEY,
            "Accept": "application/json"
        }
        if not HEVY_API_KEY:
            raise ValueError("API Key não encontrada no config.py. Defina HEVY_API_KEY nele.")

    def fetch_all_workouts(self):
        """Busca todos os treinos da API tratando a paginação"""
        workouts = []
        page = 1
        page_size = 10  # Limite padrão comum de paginação
        
        while True:
            url = f"{BASE_URL}/v1/workouts"
            params = {"page": page, "pageSize": page_size}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                raise Exception(f"Erro ao buscar treinos (Status {response.status_code}): {response.text}")
                
            data = response.json()
            # Dependendo da API do Hevy, pode vir direto uma lista ou um dicionário com uma chave 'workouts'
            # Vamos tratar os dois cenários baseados na estrutura padrão do Swagger
            batch = data.get("workouts", data) if isinstance(data, dict) else data
            
            if not batch:
                break
                
            workouts.extend(batch)
            if len(batch) < page_size:
                break
                
            page += 1
            
        return workouts

    def process_and_save(self, workouts_json):
        """Processa os dados brutos em um modelo relacional (Star Schema) e salva no SQLite"""
        workouts_list = []
        exercises_list = []
        sets_list = []

        for w in workouts_json:
            # 1. Tabela Fato/Dimensão Treinos (Workouts)
            workouts_list.append({
                "workout_id": w.get("id"),
                "title": w.get("title"),
                "description": w.get("description"),
                "start_time": w.get("start_time"),
                "end_time": w.get("end_time"),
                "duration_seconds": w.get("duration_seconds") or 0,
            })

            # Iterar pelos exercícios do treino
            for idx_e, e in enumerate(w.get("exercises", [])):
                workout_exercise_id = f"{w.get('id')}_{idx_e}"
                
                # 2. Tabela Auxiliar Relacional de Exercícios por Treino
                exercises_list.append({
                    "workout_exercise_id": workout_exercise_id,
                    "workout_id": w.get("id"),
                    "exercise_template_id": e.get("exercise_template_id"),
                    "title": e.get("title"),
                    "notes": e.get("notes")
                })

                # Iterar pelas séries (sets) de cada exercício
                for s in e.get("sets", []):
                    sets_list.append({
                        "set_id": s.get("id"),
                        "workout_exercise_id": workout_exercise_id,
                        "set_index": s.get("index"),
                        "weight_kg": s.get("weight_kg"),
                        "reps": s.get("reps"),
                        "rpe": s.get("rpe"),
                        "type": s.get("type") # 'normal', 'warmup', 'drop', 'failure'
                    })

        # Converter para DataFrames do Pandas
        df_workouts = pd.DataFrame(workouts_list)
        df_exercises = pd.DataFrame(exercises_list)
        df_sets = pd.DataFrame(sets_list)

        # Salvar tudo no SQLite
        conn = sqlite3.connect(self.db_name)
        
        df_workouts.to_sql("workouts", conn, if_exists="replace", index=False)
        df_exercises.to_sql("workout_exercises", conn, if_exists="replace", index=False)
        df_sets.to_sql("exercise_sets", conn, if_exists="replace", index=False)
        
        conn.close()
        return len(df_workouts), len(df_sets)