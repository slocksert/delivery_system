# Sistema de Otimização de Rede de Entregas

Sistema avançado que modela uma rede de entrega como um grafo para otimizar o fluxo de entregas com rastreamento em tempo real e análise de desempenho.

## ✨ Principais Funcionalidades

### 🌍 Geração Automática de Redes de Maceió
Crie automaticamente redes completas de entregas para Maceió usando dados geográficos reais!

### 📡 Rastreamento em Tempo Real  
Sistema de WebSocket para monitoramento ao vivo de veículos e entregas com interface visual.

### 🔐 Sistema de Autenticação e Permissões
Controle de acesso baseado em roles (Admin, Operador, Visualizador) com JWT.

### 📊 Análise e Otimização de Fluxo
Algoritmos de otimização de rotas com análise de capacidade e estatísticas em tempo real.

## 🚀 Como usar a Geração Automática:

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

### Parâmetros disponíveis:
- `num_clientes`: Número de clientes a serem gerados (padrão: 100)
- `nome_rede`: Nome personalizado para a rede (opcional)

### O que é gerado automaticamente:
- ✅ **2 Depósitos** estratégicos em Maceió
- ✅ **Múltiplos Hubs** logísticos distribuídos pela cidade
- ✅ **N Clientes** (configurável) espalhados pela região
- ✅ **5 Zonas** de entrega otimizadas
- ✅ **Frota de veículos** adequada para a demanda
- ✅ **Rotas completas** conectando todos os pontos
- ✅ **Posicionamento geográfico realista** usando dados de Maceió

## 🏗️ Estrutura do Projeto

### Backend (API REST + WebSocket)
- `src/backend/main.py` - Aplicação FastAPI principal
- `src/backend/api/` - Endpoints da API (auth, rede, integração, websocket)
- `src/backend/services/` - Lógica de negócio (rede_service, vehicle_movement_service)
- `src/backend/auth/` - Sistema de autenticação JWT
- `src/backend/database/` - Persistência de dados com SQLite

### Core (Lógica de Domínio)
- `src/core/entities/` - Modelos das entidades (Deposito, Hub, Cliente, etc.)
- `src/core/data/` - Utilitários para carregamento e manipulação de dados
- `src/core/generators/` - Gerador automático de redes de Maceió
- `src/core/algorithms/` - Algoritmos de otimização de fluxo

### Frontend (Interface Visual)
- `frontend/templates/` - Interface web para visualização em tempo real
- `frontend/static/` - Recursos estáticos (CSS, JS)

### Testes
- `test_models.py` - Testes das entidades principais
- `test_backend_behaviors.py` - Testes comportamentais da API  
- `test_auth_behaviors.py` - Testes do sistema de autenticação

## 🏃‍♂️ Como Executar

### Pré-requisitos
```bash
# Instalar dependências
pip install -r requirements.txt
```

### Iniciar o Servidor
```bash
# Iniciar servidor FastAPI com todas as funcionalidades
PYTHONPATH=./src python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Acessar o Sistema
- **API Interativa:** http://localhost:8000/docs
- **Interface Visual:** http://localhost:8000/app
- **API Root:** http://localhost:8000/api
- **Health Check:** http://localhost:8000/health

### 🎯 Demonstração Rápida
```bash
# 1. Criar uma rede de Maceió com 50 clientes
curl -X POST "http://localhost:8000/api/v1/rede/criar-maceio-completo?num_clientes=50" \
  -H "Authorization: Bearer $(curl -s -X POST 'http://localhost:8000/api/v1/auth/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=secret' | jq -r '.access_token')"

# 2. Abrir http://localhost:8000/app para visualizar em tempo real
```

## 🧪 Executar Testes

```bash
# Executar todos os testes
pytest

# Executar com mais detalhes
pytest -v

# Testar entidades principais
pytest test_models.py -v

# Testar funcionalidades da API
pytest test_backend_behaviors.py -v

# Testar sistema de autenticação
pytest test_auth_behaviors.py -v

# Testar funcionalidade específica (exemplo)
pytest test_backend_behaviors.py::TestNetworkManagement::test_system_generates_complete_maceio_networks_on_demand -v
```

## 📋 Endpoints da API

### 🔐 Autenticação
- `POST /api/v1/auth/login` - Login via formulário  
- `POST /api/v1/auth/login-json` - Login via JSON
- `POST /api/v1/auth/register` - Registro de novo usuário
- `GET /api/v1/auth/me` - Informações do usuário atual
- `GET /api/v1/auth/verify-token` - Validação de token
- `GET /api/v1/auth/users` - Listar usuários (admin)
- `PUT /api/v1/auth/users/{username}` - Atualizar usuário (admin)
- `DELETE /api/v1/auth/users/{username}` - Deletar usuário (admin)

### 🌐 Redes de Entrega
- `POST /api/v1/rede/criar` - Criar rede personalizada (JSON)
- `POST /api/v1/rede/criar-maceio-completo` - **🆕 Criar rede automática de Maceió**
- `GET /api/v1/rede/listar` - Listar todas as redes
- `GET /api/v1/rede/{id}` - Dados completos da rede
- `GET /api/v1/rede/{id}/info` - Informações detalhadas da rede
- `GET /api/v1/rede/{id}/validar` - Validar rede
- `GET /api/v1/rede/{id}/estatisticas` - Estatísticas da rede
- `GET /api/v1/rede/{id}/nos` - Listar nós da rede

### 🚚 Controle de Movimento (Tempo Real)
- `POST /api/v1/rede/{id}/start-movement` - Iniciar movimento de veículos
- `POST /api/v1/rede/{id}/stop-movement` - Parar movimento de veículos  
- `GET /api/v1/rede/{id}/delivery-stats` - Estatísticas de entrega
- `POST /api/v1/rede/{id}/reset-deliveries` - Resetar sistema de entregas

### 🔗 Integração de Dados
- `GET /api/v1/integracao/status` - Status do serviço
- `POST /api/v1/integracao/importar/json-data` - Importar dados JSON direto
- `POST /api/v1/integracao/importar/json` - Upload de arquivo JSON
- `POST /api/v1/integracao/importar/csv` - Upload de arquivo CSV
- `GET /api/v1/integracao/exemplo/json` - Exemplo de formato JSON
- `GET /api/v1/integracao/exemplo/csv` - Exemplo de formato CSV

### 📡 WebSocket (Rastreamento Tempo Real)
- `WS /ws/{rede_id}` - Conexão WebSocket para dados em tempo real
- Eventos: posições de veículos, estatísticas, alertas de tráfego

### 🏥 Sistema
- `GET /` - Redirecionamento para aplicação
- `GET /api` - Informações da API  
- `GET /app` - Interface web de visualização
- `GET /health` - Verificação de saúde dos serviços

## 🛡️ Sistema de Permissões

### Roles Disponíveis:
- **👑 Admin**: Acesso completo (criar, ler, atualizar, deletar + gerenciar usuários)
- **⚡ Operator**: Criar e modificar redes (criar, ler, atualizar)  
- **👁️ Viewer**: Apenas visualização (ler)

### Usuários Padrão:
- `admin/secret` - Administrador completo
- `operator/secret` - Operador de redes
- `viewer/secret` - Visualizador somente leitura

## 🎮 Interface Visual

Acesse `http://localhost:8000/app` para uma interface web completa com:

- 🗺️ **Mapa interativo** de Maceió com a rede de entregas
- 🚛 **Rastreamento em tempo real** dos veículos  
- 📊 **Painéis de estatísticas** ao vivo
- 🔄 **Controles de movimento** (play/pause/reset)
- 📡 **Conexão WebSocket** para atualizações automáticas
- 🎯 **Indicadores de status** de conexão e saúde do sistema

## ⚡ WebSocket - Tempo Real

O sistema oferece rastreamento em tempo real via WebSocket:

```javascript
// Conectar ao WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/REDE_ID');

// Receber atualizações em tempo real
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    // data.posicoes_veiculos - posições atuais
    // data.estatisticas - métricas em tempo real
    // data.rotas_ativas - rotas sendo executadas
};
```

## 🔧 Tecnologias Utilizadas

### Backend
- **FastAPI** - Framework web moderno e rápido
- **SQLite** - Banco de dados leve e eficiente
- **JWT** - Autenticação baseada em tokens
- **WebSocket** - Comunicação em tempo real
- **NetworkX** - Algoritmos de grafos
- **Pydantic** - Validação de dados

### Frontend  
- **Leaflet** - Mapas interativos
- **JavaScript** - Interface dinâmica
- **WebSocket API** - Atualizações em tempo real

### Dados Geográficos
- **OSMnx** - Dados reais de ruas de Maceió (opcional)
- **Haversine** - Cálculos de distância geográfica

## 🧩 Cobertura dos Testes

### ✅ Funcionalidades Testadas:
- **Entidades principais** - Criação e validação de modelos
- **Geração automática de redes** - Algoritmos de Maceió
- **Sistema de autenticação** - Login, registro, permissões
- **API REST** - Todos os endpoints principais
- **Controle de acesso** - Roles e autorizações
- **Integração de dados** - Importação JSON/CSV
- **Tratamento de erros** - Validação e casos extremos
- **Operações de banco** - CRUD e persistência
- **Fluxos completos** - Cenários de uso real

### 📊 Estatísticas:
- **Testes comportamentais** seguindo padrões do Google
- **Isolamento de banco** para cada teste
- **Cobertura de casos extremos** e tratamento de erros
- **Testes de segurança** e autenticação

## 🚀 Próximas Funcionalidades

- [ ] **Otimização inteligente de rotas** com ML
- [ ] **Previsão de demanda** baseada em histórico  
- [ ] **Alertas automáticos** de congestionamento
- [ ] **Dashboard analytics** avançado
- [ ] **API mobile** para entregadores
- [ ] **Integração com mapas externos** (Google Maps)
- [ ] **Relatórios automatizados** PDF/Excel

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Execute os testes (`pytest -v`)
4. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
5. Push para a branch (`git push origin feature/AmazingFeature`)
6. Abra um Pull Request

### 📝 Padrões do Projeto:
- **Testes comportamentais** (BDD-style)
- **Isolamento de dependências** em testes
- **Documentação de API** automática
- **Type hints** obrigatórios
- **Validação Pydantic** para dados
