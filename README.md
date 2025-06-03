# Sistema de Otimização de Rede de Entregas

Sistema que modela uma rede de entrega como um grafo para otimizar o fluxo de entregas.

## Estrutura do Projeto

- `src/core/entities/` - Modelos das entidades (Deposito, Hub, Cliente, etc.)
- `src/core/data/` - Utilitários para carregamento de dados
- `src/core/generators/` - Gerador de dados para Maceió
- `test_models.py` - Testes da implementação

## Executar Testes

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar todos os testes
pytest

# Executar com mais detalhes
pytest -v

# Executar teste específico
pytest test_models.py::TestEntidades::test_deposito_criacao
```

## Cobertura dos Testes

- Criação de entidades básicas
- Funcionalidades da rede de entrega
- Sistema de rotas e capacidades
- Gerador de dados
- Carregamento de JSON
- Validações e casos limite
