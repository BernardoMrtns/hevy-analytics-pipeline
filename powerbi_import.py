import sqlite3
import pandas as pd

# Caminho absoluto para o banco de dados local
# (Ajuste se clonar o repositório em outro computador)
caminho_db = r"C:\Dev\hevy-analytics-pipeline\hevy_analytics.db"

# Estabelece a conexão com o banco SQLite
conn = sqlite3.connect(caminho_db)

# Extrai as tabelas principais (Fato e Dimensões)
df_workouts = pd.read_sql_query("SELECT * FROM workouts", conn)
df_exercises = pd.read_sql_query("SELECT * FROM workout_exercises", conn)
df_sets = pd.read_sql_query("SELECT * FROM exercise_sets", conn)

# Extrai a tabela auxiliar de higienização de grupos musculares
dim_grupos_musculares = pd.read_sql_query("SELECT * FROM dim_grupos_musculares", conn)

# Fecha a conexão para liberar o arquivo
conn.close()