import sqlite3
import pandas as pd
from rich.console import Console

console = Console()

def create_muscle_mapping():
    db_path = "hevy_analytics.db"
    conn = sqlite3.connect(db_path)
    
    # Busca todos os exercícios únicos que você já registrou
    query = "SELECT DISTINCT exercise_template_id, title FROM workout_exercises"
    df_exercises = pd.read_sql_query(query, conn)
    
    # Função para categorizar o grupo muscular por palavra-chave
    def assign_muscle_group(title):
        t = str(title).lower()
        if any(x in t for x in ['supino', 'bench press', 'chest', 'crucifixo', 'peck', 'fly', 'peito', 'chest']):
            return 'Peito'
        elif any(x in t for x in ['puxada', 'pulldown', 'remada', 'row', 'costas', 'lat ', 'chin up', 'pull up']):
            return 'Costas'
        elif any(x in t for x in ['leg press', 'agachamento', 'squat', 'extensora', 'flexora', 'panturrilha', 'calf', 'adutora', 'abdutora', 'hack']):
            return 'Pernas'
        elif any(x in t for x in ['desenvolvimento', 'shoulder', 'elevação lateral', 'elevação frontal', 'ombro', 'posterior (na máquina)']):
            return 'Ombros'
        elif any(x in t for x in ['rosca', 'curl', 'biceps', 'bíceps']):
            return 'Bíceps'
        elif any(x in t for x in ['tríceps', 'triceps', 'skullcrusher', 'fundos', 'dip']):
            return 'Tríceps'
        elif any(x in t for x in ['abdominal', 'crunch', 'core', 'plank']):
            return 'Abdômen'
        else:
            return 'Outros'

    # Função para limpar e unificar os nomes das duplicatas
    def normalize_name(title):
        t = str(title).lower()
        if 'leg press' in t: return 'Leg Press'
        if 'puxada' in t or 'pulldown' in t: return 'Puxada Alta'
        if 'supino inclinado' in t or 'incline bench' in t: return 'Supino Inclinado'
        if 'supino' in t or 'bench press' in t: return 'Supino Reto'
        if 'rosca scott' in t or 'preacher curl' in t: return 'Rosca Scott'
        if 'remada' in t or 'row' in t: return 'Remada'
        if 'chest fly' in t or 'crucifixo' in t: return 'Crucifixo'
        if 'elevação lateral' in t or 'lateral raise' in t: return 'Elevação Lateral'
        return str(title).title()

    # Aplica as transformações
    df_exercises['Grupo Muscular'] = df_exercises['title'].apply(assign_muscle_group)
    df_exercises['Nome Normalizado'] = df_exercises['title'].apply(normalize_name)
    
    # Salva a nova dimensão no banco de dados SQLite
    df_exercises.to_sql("dim_grupos_musculares", conn, if_exists="replace", index=False)
    conn.close()
    
    console.print("[bold green]✅ Tabela 'dim_grupos_musculares' criada e higienizada com sucesso![/bold green]")
    console.print("Exercícios categorizados: ", len(df_exercises))

if __name__ == "__main__":
    create_muscle_mapping()