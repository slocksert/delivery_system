from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from ..models.schemas import (
    NetworkCreate,
    StatusResponse,
    NetworkResponse
)
from ..services.rede_service import RedeService
from ..dependencies import get_rede_service
from ..auth.auth import (
    require_read_permission,
    require_write_permission,
    require_admin_permission,
    User
)
from typing import List, Dict, Any
import json
import csv
import io

router = APIRouter(
    prefix="/integracao",
    tags=["Integração e Importação"],
    responses={
        400: {"description": "Dados inválidos"},
        422: {"description": "Erro de processamento"}
    }
)

@router.post(
    "/importar/json",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar rede de arquivo JSON",
    description="Importa uma rede de entrega a partir de um arquivo JSON"
)
async def importar_json(
    arquivo: UploadFile = File(..., description="Arquivo JSON com dados da rede"),
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    """
    **Importar Rede de JSON**
    
    Importa uma rede de entrega completa a partir de um arquivo JSON.
    
    **Formato esperado do JSON:**
    ```json
    {
        "nome": "Rede São Paulo",
        "descricao": "Rede de entregas da região metropolitana",
        "nodes": [
            {
                "id": "dep_01",
                "nome": "Depósito Central",
                "tipo": "deposito",
                "latitude": -23.550520,
                "longitude": -46.633308
            }
        ],
        "edges": [
            {
                "origem": "dep_01",
                "destino": "hub_01", 
                "capacidade": 100,
                "distancia": 5.5
            }
        ]
    }
    ```
    """
    try:
        # Verificar tipo do arquivo
        if not arquivo.filename or not arquivo.filename.endswith('.json'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo deve ter extensão .json"
            )
        
        # Ler conteúdo do arquivo
        conteudo = await arquivo.read()
        
        try:
            dados = json.loads(conteudo.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"JSON inválido: {str(e)}"
            )
        
        # Validar estrutura básica
        campos_obrigatorios = ['nome', 'nodes', 'edges']
        for campo in campos_obrigatorios:
            if campo not in dados:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Campo obrigatório '{campo}' não encontrado"
                )
        
        # Criar rede usando o serviço
        rede_id = rede_service.criar_rede_schema(dados)
        
        return StatusResponse(
            status="success",
            message=f"Rede '{dados['nome']}' importada com sucesso do arquivo JSON",
            data={
                "rede_id": rede_id,
                "arquivo": arquivo.filename,
                "total_nodes": len(dados['nodes']),
                "total_edges": len(dados['edges'])
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar arquivo: {str(e)}"
        )

@router.post(
    "/importar/csv-nodes",
    response_model=StatusResponse,
    summary="Importar nós de arquivo CSV",
    description="Importa nós da rede a partir de um arquivo CSV"
)
async def importar_csv_nodes(
    arquivo: UploadFile = File(..., description="Arquivo CSV com dados dos nós"),
    nome_rede: str = "Rede Importada CSV",
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    """
    **Importar Nós de CSV**
    
    Importa nós da rede a partir de um arquivo CSV.
    
    **Formato esperado do CSV:**
    ```csv
    id,nome,tipo,latitude,longitude
    dep_01,Depósito Central,deposito,-23.550520,-46.633308
    hub_01,Hub Norte,hub,-23.530520,-46.623308
    zona_01,Zona Vila Madalena,zona,-23.560520,-46.643308
    ```
    
    **Colunas obrigatórias:** id, nome, tipo, latitude, longitude
    """
    try:
        # Verificar tipo do arquivo
        if not arquivo.filename or not arquivo.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo deve ter extensão .csv"
            )
        
        # Ler conteúdo do arquivo
        conteudo = await arquivo.read()
        csv_texto = conteudo.decode('utf-8')
        
        # Processar CSV
        csv_reader = csv.DictReader(io.StringIO(csv_texto))
        
        # Verificar colunas obrigatórias
        colunas_obrigatorias = {'id', 'nome', 'tipo', 'latitude', 'longitude'}
        colunas_arquivo = set(csv_reader.fieldnames or [])
        
        if not colunas_obrigatorias.issubset(colunas_arquivo):
            faltando = colunas_obrigatorias - colunas_arquivo
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Colunas obrigatórias faltando: {', '.join(faltando)}"
            )
        
        # Processar linhas
        nodes = []
        for i, linha in enumerate(csv_reader, 1):
            try:
                node = {
                    "id": linha['id'].strip(),
                    "nome": linha['nome'].strip(),
                    "tipo": linha['tipo'].strip().lower(),
                    "latitude": float(linha['latitude']),
                    "longitude": float(linha['longitude'])
                }
                
                # Validar tipo
                if node['tipo'] not in ['deposito', 'hub', 'zona']:
                    raise ValueError(f"Tipo inválido: {node['tipo']}. Use: deposito, hub, zona")
                
                nodes.append(node)
                
            except (ValueError, KeyError) as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Erro na linha {i}: {str(e)}"
                )
        
        if not nodes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nenhum nó válido encontrado no arquivo"
            )
        
        # Criar dados da rede (sem arestas por enquanto)
        dados_rede = {
            "nome": nome_rede,
            "descricao": f"Rede importada de {arquivo.filename}",
            "nodes": nodes,
            "edges": []  # Será preenchido posteriormente ou em outro endpoint
        }
        
        # Criar rede
        rede_id = rede_service.criar_rede_schema(dados_rede)
        
        return StatusResponse(
            status="success",
            message=f"Nós importados com sucesso. Rede '{nome_rede}' criada",
            data={
                "rede_id": rede_id,
                "arquivo": arquivo.filename,
                "total_nodes": len(nodes),
                "tipos_importados": {
                    "deposito": len([n for n in nodes if n['tipo'] == 'deposito']),
                    "hub": len([n for n in nodes if n['tipo'] == 'hub']),
                    "zona": len([n for n in nodes if n['tipo'] == 'zona'])
                },
                "aviso": "Rede criada apenas com nós. Adicione rotas usando outros endpoints."
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar arquivo CSV: {str(e)}"
        )

@router.post(
    "/importar/json-data",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar rede de dados JSON",
    description="Importa uma rede de entrega a partir de dados JSON no request body"
)
async def importar_json_data(
    dados_rede: NetworkCreate,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    """
    **Importar Rede de Dados JSON**
    
    Importa uma rede de entrega diretamente dos dados JSON no request body.
    Alternativa ao upload de arquivo para testes e integrações diretas.
    """
    try:
        # Converter para dict para compatibilidade com o serviço
        dados_dict = {
            "nome": dados_rede.nome,
            "descricao": dados_rede.descricao or "",
            "nodes": [node.model_dump() for node in dados_rede.nodes],
            "edges": [edge.model_dump() for edge in dados_rede.edges]
        }
        
        # Criar rede usando o serviço
        rede_id = rede_service.criar_rede_schema(dados_dict)
        
        return StatusResponse(
            status="success",
            message=f"Rede '{dados_rede.nome}' criada com sucesso via dados JSON",
            data={
                "rede_id": rede_id,
                "total_nodes": len(dados_rede.nodes),
                "total_edges": len(dados_rede.edges)
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar dados: {str(e)}"
        )

@router.get(
    "/exemplo/json",
    summary="Obter exemplo de JSON",
    description="Retorna um exemplo de arquivo JSON para importação"
)
async def obter_exemplo_json(
    current_user: User = Depends(require_read_permission)
) -> Dict[str, Any]:
    """
    **Exemplo de JSON para Importação**
    
    Retorna um exemplo completo de arquivo JSON que pode ser usado
    para importar uma rede de entregas.
    """
    return {
        "exemplo": {
            "nome": "Rede São Paulo Centro",
            "descricao": "Rede de entregas da região central de São Paulo",
            "nodes": [
                {
                    "id": "dep_central",
                    "nome": "Depósito Central Brás",
                    "tipo": "deposito",
                    "latitude": -23.550520,
                    "longitude": -46.633308
                },
                {
                    "id": "hub_norte",
                    "nome": "Hub Zona Norte",
                    "tipo": "hub", 
                    "latitude": -23.530520,
                    "longitude": -46.623308
                },
                {
                    "id": "hub_sul",
                    "nome": "Hub Zona Sul",
                    "tipo": "hub",
                    "latitude": -23.570520,
                    "longitude": -46.643308
                },
                {
                    "id": "zona_vila_madalena",
                    "nome": "Zona Vila Madalena",
                    "tipo": "zona",
                    "latitude": -23.560520,
                    "longitude": -46.653308
                },
                {
                    "id": "zona_moema",
                    "nome": "Zona Moema",
                    "tipo": "zona",
                    "latitude": -23.580520,
                    "longitude": -46.633308
                }
            ],
            "edges": [
                {
                    "origem": "dep_central",
                    "destino": "hub_norte",
                    "capacidade": 150,
                    "distancia": 12.5
                },
                {
                    "origem": "dep_central", 
                    "destino": "hub_sul",
                    "capacidade": 120,
                    "distancia": 8.3
                },
                {
                    "origem": "hub_norte",
                    "destino": "zona_vila_madalena",
                    "capacidade": 80,
                    "distancia": 15.2
                },
                {
                    "origem": "hub_sul",
                    "destino": "zona_moema", 
                    "capacidade": 100,
                    "distancia": 6.7
                }
            ]
        },
        "instrucoes": {
            "1": "Salve o conteúdo 'exemplo' em um arquivo .json",
            "2": "Use o endpoint POST /integracao/importar/json para enviar o arquivo",
            "3": "A rede será criada automaticamente com todos os nós e rotas"
        }
    }

@router.get(
    "/exemplo/csv",
    summary="Obter exemplo de CSV",
    description="Retorna um exemplo de arquivo CSV para importação de nós"
)
async def obter_exemplo_csv(
    current_user: User = Depends(require_read_permission)
) -> Dict[str, Any]:
    """
    **Exemplo de CSV para Importação**
    
    Retorna um exemplo de arquivo CSV que pode ser usado
    para importar nós de uma rede.
    """
    return {
        "exemplo_csv": "id,nome,tipo,latitude,longitude\ndep_01,Depósito Central,deposito,-23.550520,-46.633308\nhub_01,Hub Norte,hub,-23.530520,-46.623308\nhub_02,Hub Sul,hub,-23.570520,-46.643308\nzona_01,Zona Vila Madalena,zona,-23.560520,-46.653308\nzona_02,Zona Moema,zona,-23.580520,-46.633308",
        "instrucoes": {
            "1": "Crie um arquivo .csv com as colunas: id,nome,tipo,latitude,longitude",
            "2": "Tipos válidos: deposito, hub, zona",
            "3": "Use coordenadas em graus decimais (ex: -23.550520)",
            "4": "Envie via POST /integracao/importar/csv-nodes"
        },
        "colunas_obrigatorias": ["id", "nome", "tipo", "latitude", "longitude"],
        "tipos_validos": ["deposito", "hub", "zona"]
    }

@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Status do serviço de integração",
    description="Verifica o status do serviço de integração"
)
async def status_integracao(
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_read_permission)
) -> StatusResponse:
    """
    **Status da Integração**
    
    Verifica o status do serviço de integração e estatísticas básicas.
    """
    try:
        redes = rede_service.listar_redes()
        
        return StatusResponse(
            status="operational",
            message="Serviço de integração funcionando normalmente",
            data={
                "total_redes_cadastradas": len(redes),
                "formatos_suportados": ["JSON", "CSV"],
                "endpoints_disponiveis": [
                    "/integracao/importar/json",
                    "/integracao/importar/csv-nodes",
                    "/integracao/exemplo/json",
                    "/integracao/exemplo/csv"
                ],
                "dev_responsavel": "Dev 5 - Backend & Integration"
            }
        )
        
    except Exception as e:
        return StatusResponse(
            status="error",
            message="Erro no serviço de integração",
            data={"erro": str(e)}
        )