# Sistema de Otimização de Rede de Entregas

## Descrição do Projeto

Este projeto implementa um sistema de otimização para redes de entrega urbanas, modelando a infraestrutura logística como um grafo direcionado. O sistema permite a criação, visualização e análise de redes de distribuição, com foco especial na cidade de Maceió/AL, utilizando dados geográficos reais para simulação de cenários logísticos.

### Características Principais

- **Modelagem de Grafos**: Representação de depósitos, hubs, clientes e rotas como estruturas de grafos
- **Geração Automática**: Criação de redes completas baseadas em dados geográficos reais de Maceió
- **Rastreamento em Tempo Real**: Sistema de monitoramento de veículos via WebSocket
- **Análise de Fluxo**: Algoritmos de otimização de rotas e análise de capacidade
- **Interface Web**: Visualização interativa com mapas e painéis de controle
- **Sistema de Autenticação**: Controle de acesso baseado em roles com JWT
- **API REST**: Endpoints completos para integração e manipulação de dados

### Tecnologias Utilizadas

- **Backend**: FastAPI, SQLite, NetworkX, OSMnx
- **Frontend**: JavaScript, Leaflet Maps, WebSocket API
- **Testes**: pytest, pytest-asyncio
- **Autenticação**: JWT (JSON Web Tokens)
- **Dados Geográficos**: OpenStreetMap (via OSMnx)

## Configuração do Ambiente

### Pré-requisitos

- Python 3.12+
- pip (gerenciador de pacotes Python)

### Instalação das Dependências

```bash
# Clonar o repositório (se aplicável)
# git clone <repository-url>
# cd delivery_system

# Instalar dependências
pip install -r requirements.txt
```

### Configuração do Banco de Dados

O sistema utiliza SQLite e cria automaticamente o banco de dados na primeira execução. Não é necessária configuração adicional.

## Execução do Sistema

### Iniciar o Servidor

```bash
# Definir o PYTHONPATH e iniciar o servidor FastAPI
PYTHONPATH=./src python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Acessos do Sistema

- **Documentação da API**: http://localhost:8000/docs
- **Interface Web**: http://localhost:8000/app
- **Endpoint da API**: http://localhost:8000/api
- **Health Check**: http://localhost:8000/health

### Credenciais de Acesso

O sistema vem com usuários pré-configurados:

- **Administrador**: `admin` / `secret`
- **Operador**: `operator` / `secret`  
- **Visualizador**: `viewer` / `secret`

## Execução dos Testes

### Executar Todos os Testes

```bash
pytest -v
```

### Executar Testes Específicos

```bash
# Testes das entidades do domínio
pytest test/test_models.py -v

# Testes comportamentais da API
pytest test/test_backend_behaviors.py -v

# Testes do sistema de autenticação
pytest test/test_auth_behaviors.py -v

# Teste específico
pytest test/test_backend_behaviors.py::TestNetworkManagement::test_system_generates_complete_maceio_networks_on_demand -v
```

### Cobertura dos Testes

Os testes cobrem:
- Criação e validação de entidades
- Funcionalidades da API REST
- Sistema de autenticação e autorização
- Geração automática de redes
- Integração de dados (JSON/CSV)
- Operações de banco de dados
- Tratamento de erros e casos extremos

## Estrutura do Projeto

```
delivery_system/
├── src/
│   ├── backend/           # API REST e WebSocket
│   │   ├── api/          # Endpoints (auth, rede, integração, websocket)
│   │   ├── services/     # Lógica de negócio
│   │   ├── auth/         # Sistema de autenticação
│   │   └── database/     # Persistência de dados
│   └── core/             # Lógica de domínio
│       ├── entities/     # Modelos (Deposito, Hub, Cliente, etc.)
│       ├── algorithms/   # Algoritmos de otimização
│       ├── generators/   # Gerador de redes de Maceió
│       └── data/         # Utilitários de dados
├── frontend/             # Interface web
│   ├── templates/        # Páginas HTML
│   └── static/          # CSS, JavaScript
├── test/                # Testes automatizados
├── requirements.txt     # Dependências Python
└── README.md           # Este arquivo
```

## Funcionalidades Principais

### 1. Geração Automática de Redes

O sistema pode gerar automaticamente redes de entrega para Maceió:

```bash
# Exemplo via curl
curl -X POST "http://localhost:8000/api/v1/rede/criar-maceio-completo?num_clientes=100&nome_rede=Rede_Teste" \
  -H "Authorization: Bearer <TOKEN>"
```

### 2. Visualização em Tempo Real

A interface web permite:
- Visualização da rede em mapa interativo
- Rastreamento de veículos em tempo real
- Painéis de estatísticas dinâmicas
- Controles de simulação (iniciar/parar movimento)

### 3. API REST Completa

O sistema oferece endpoints para:
- Autenticação e autorização
- CRUD de redes de entrega
- Integração de dados externos
- Controle de movimento de veículos
- Consulta de estatísticas

### 4. Sistema de Permissões

Três níveis de acesso:
- **Admin**: Acesso completo + gerenciamento de usuários
- **Operator**: Criar e modificar redes
- **Viewer**: Apenas visualização

## Algoritmos Implementados

### Otimização de Fluxo
- Cálculo de capacidade máxima de rotas
- Análise de gargalos na rede
- Distribuição otimizada de demanda

### Geração Geográfica
- Posicionamento estratégico de depósitos
- Distribuição inteligente de hubs
- Criação de zonas de entrega baseadas em densidade populacional

### Simulação de Movimento
- Cálculo de rotas em tempo real
- Simulação de tráfego urbano
- Rastreamento de entregas e estatísticas

## Considerações Técnicas

### Performance
- Cache de redes em memória para acesso rápido
- Lazy loading de dados geográficos pesados
- WebSocket otimizado para múltiplas conexões

### Escalabilidade
- Arquitetura modular com separação clara de responsabilidades
- Database leve (SQLite) adequado para desenvolvimento e demonstração
- API RESTful seguindo padrões de mercado

### Testes
- Cobertura abrangente com isolamento de dependências
- Testes comportamentais seguindo padrões BDD
- Simulação de cenários reais de uso

## Licença

Este projeto foi desenvolvido para fins acadêmicos e de demonstração.
