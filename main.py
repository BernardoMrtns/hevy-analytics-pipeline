import argparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from pipeline import HevyPipeline
import os

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Iron Metrics Pipeline - Hevy API to Power BI")
    parser.add_argument("command", choices=["sync"], help="Comando para executar (ex: sync)")
    args = parser.parse_args()

    if args.command == "sync":
        console.print("[bold cyan]🏋️‍♂️ Iniciando Sincronização com a API do Hevy...[/bold cyan]")
        
        # Verifica se o config existe localmente antes de rodar
        if not os.path.exists("config.py"):
            console.print("[bold red]❌ Erro:[/bold red] O arquivo 'config.py' não foi encontrado neste diretório.")
            console.print("Por favor, crie um arquivo 'config.py' contendo: [green]HEVY_API_KEY = 'sua_chave'[/green]")
            return

        try:
            pipeline = HevyPipeline()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True
            ) as progress:
                
                # Passo 1: Buscar dados da API
                progress.add_task(description="Buscando histórico de treinos da API...", total=None)
                raw_workouts = pipeline.fetch_all_workouts()
                
                # Passo 2: Processar e salvar no SQLite
                progress.add_task(description="Modelando dados e atualizando banco SQLite...", total=None)
                num_workouts, num_sets = pipeline.process_and_save(raw_workouts)
                
            console.print(f"[bold green]✨ Sincronização concluída com sucesso![/bold green]")
            console.print(f"📊 [bold]{num_workouts}[/bold] treinos importados.")
            console.print(f"💪 [bold]{num_sets}[/bold] séries/sets de exercícios estruturados.")
            console.print(f"📁 Banco de dados atualizado: [yellow]hevy_analytics.db[/yellow]")
            console.print("\n[bold blue]🚀 Pronto para abrir no Power BI![/bold blue]")

        except Exception as e:
            console.print(f"[bold red]❌ O pipeline falhou:[/bold red] {str(e)}")

if __name__ == "__main__":
    main()