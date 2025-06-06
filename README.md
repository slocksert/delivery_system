# Sistema de Otimização de Rede de Entregas

Sistema que modela uma rede de entrega como um grafo para otimizar o fluxo de entregas.

## 🚀 Nova Funcionalidade: Geração Automática de Redes de Maceió

Agora você pode criar automaticamente uma rede completa de entregas para Maceió sem precisar enviar JSON ou arquivos!

### Como usar:

**Via API REST:**
```bash
# 1. Fazer login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret"

# 2. Criar rede completa de Maceió (usando o token obtido)
curl -X POST "http://localhost:8000/api/v1/rede/criar-maceio-completo?num_clientes=100&nome_rede=Minha Rede" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"
```

**Via Python (exemplo incluído):**
```bash
python exemplo_uso_maceio.py
```

### Parâmetros disponíveis:
- `num_clientes`: Número de clientes a serem gerados (padrão: 100)
- `nome_rede`: Nome personalizado para a rede (opcional)

### O que é gerado automaticamente:
- ✅ **2 Depósitos** estratégicos em Maceió
- ✅ **12 Hubs** logísticos distribuídos pela cidade
- ✅ **N Clientes** (configurável) espalhados pela região
- ✅ **5 Zonas** de entrega otimizadas
- ✅ **Frota de veículos** adequada para a demanda
- ✅ **Rotas completas** conectando todos os pontos

## Estrutura do Projeto

- `src/core/entities/` - Modelos das entidades (Deposito, Hub, Cliente, etc.)
- `src/core/data/` - Utilitários para carregamento de dados
- `src/core/generators/` - Gerador de dados para Maceió
- `src/backend/` - API REST com FastAPI
- `test_models.py` - Testes da implementação

## 🏃‍♂️ Como Executar

### Iniciar o Servidor da API:
```bash
# Instalar dependências
pip install -r requirements.txt

# Iniciar servidor FastAPI
PYTHONPATH=./src python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse: http://localhost:8000/docs para ver a documentação interativa da API

### Testar a Nova Funcionalidade:
```bash
# Executar exemplo completo
python exemplo_uso_maceio.py

# Ou execute testes específicos
pytest test_backend.py::TestNetworkEndpoints::test_create_maceio_complete_network -v
```

## Executar Testes

```bash
# Executar todos os testes
pytest

# Executar com mais detalhes
pytest -v

# Executar teste específico
pytest test_models.py::TestEntidades::test_deposito_criacao

# Executar testes da nova funcionalidade
pytest test_backend.py::TestNetworkEndpoints::test_create_maceio_complete_network -v
```

## 📋 Endpoints da API

### Autenticação
- `POST /api/v1/auth/login` - Fazer login
- `GET /api/v1/auth/me` - Informações do usuário atual

### Redes de Entrega
- `POST /api/v1/rede/criar` - Criar rede personalizada (JSON)
- `POST /api/v1/rede/criar-maceio-completo` - **🆕 Criar rede automática de Maceió**
- `GET /api/v1/rede/listar` - Listar todas as redes
- `GET /api/v1/rede/{id}/info` - Informações detalhadas da rede
- `GET /api/v1/rede/{id}/validar` - Validar rede
- `GET /api/v1/rede/{id}/estatisticas` - Estatísticas da rede

### Integração
- `POST /api/v1/integracao/importar/json-data` - Importar dados JSON
- `GET /api/v1/integracao/exemplo/json` - Exemplo de formato JSON
- `GET /api/v1/integracao/exemplo/csv` - Exemplo de formato CSV

## Cobertura dos Testes

- Criação de entidades básicas
- Funcionalidades da rede de entrega
- **🆕 Geração automática de redes de Maceió**
- Autenticação e autorização
- Endpoints da API REST
- Integração completa da aplicação
