# Hevy Analytics Pipeline

Pipeline Python simples para limpeza e processamento de dados usado como ponto de partida para análises e ETL.

## Descrição

Conjunto de scripts para extrair, limpar e processar dados em um fluxo leve. Ideal para prototipagem e integração em pipelines maiores.

## Principais arquivos

- `main.py` — Ponto de entrada para executar o pipeline.
- `pipeline.py` — Orquestra as etapas do pipeline.
- `clean_data.py` — Funções de limpeza/transformação dos dados.
- `config.py` — Configurações e parâmetros (caminhos, credenciais simuladas, flags).
- `requirements.txt` — Dependências do projeto.

## Requisitos

- Python 3.8+
- pip

## Instalação (Windows PowerShell)

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uso

Ative o ambiente virtual (veja seção "Instalação") e execute:

```powershell
python main.py
```

Ou execute etapas isoladas para desenvolvimento:

```powershell
python pipeline.py
python clean_data.py
```

## Configuração

Edite `config.py` para ajustar caminhos, nomes de arquivos, ou parâmetros do pipeline. Assegure-se de não commitar credenciais reais — use variáveis de ambiente para segredos.

## Estrutura do projeto

```
./
├─ clean_data.py
├─ config.py
├─ main.py
├─ pipeline.py
├─ requirements.txt
└─ README.md
```

## Desenvolvimento

- Siga o estilo PEP8.
- Adicione testes unitários para funções em `clean_data.py`.

## Execução em CI / Deploy

- Instale dependências a partir de `requirements.txt`.
- Configure variáveis de ambiente necessárias antes de rodar `main.py`.

## Contribuição

1. Fork o repositório
2. Crie uma branch com a sua feature (`git checkout -b feature/nome`)
3. Abra um pull request descrevendo a mudança

## Licença

Escolha uma licença (ex: MIT) e adicione um arquivo `LICENSE` se desejar.

## Contato

Para dúvidas ou sugestões, abra uma issue neste repositório.
