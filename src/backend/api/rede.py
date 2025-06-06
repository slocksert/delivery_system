from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from ..models.schemas import (
    NetworkCreate,
    PrepareFluxRequest,
    NetworkResponse,
    StatusResponse,
    NetworkInfoResponse,
)
from ..services.rede_service import RedeService
from ..dependencies import get_rede_service
from ..auth.auth import (
    require_read_permission,
    require_write_permission,
    require_admin_permission,
    User
)
from typing import List, Dict, Any, Optional

router = APIRouter(
    prefix="/rede",
    tags=["Rede de Entrega"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/criar-maceio-completo",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria automaticamente uma rede completa de Maceió",
    description="Gera automaticamente uma rede completa de entregas para Maceió com depósitos, hubs, clientes e rotas pré-configurados. Permite especificar o número de clientes e entregadores (veículos) da rede.",
)
async def criar_rede_maceio_completo(
    num_clientes: int = 100,
    num_entregadores: Optional[int] = None,
    nome_rede: Optional[str] = None,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    try:
        rede_id = rede_service.criar_rede_maceio_completo(
            num_clientes=num_clientes,
            num_entregadores=num_entregadores,
            nome_rede=nome_rede
        )
        
        msg_entregadores = f" e {num_entregadores} entregadores" if num_entregadores else ""
        return StatusResponse(
            status="success",
            message=f"Rede completa de Maceió criada com sucesso com {num_clientes} clientes{msg_entregadores}",
            data={"rede_id": rede_id}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar rede de Maceió: {str(e)}"
        )

@router.post(
    "/criar",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma nova rede de entrega.",
    description="Cria uma nova rede de entrega a partir dos dados fornecidos.",
)

async def criar_rede(
    rede_data: NetworkCreate,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    try:
        data_dict = rede_data.model_dump()
        rede_id = rede_service.criar_rede_schema(data_dict)
        
        return StatusResponse(
            status="success",
            message=f"Rede '{rede_data.nome}' criada com sucesso",
            data={"rede_id": rede_id}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro na criação da rede: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )
    

@router.get(
    "/listar",
    response_model=List[NetworkResponse],
    status_code=status.HTTP_200_OK,
    summary="Lista todas as redes.",
    description="Lista todas as redes de entrega disponíveis com informações básicas.",
) 
async def listar_rede(
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_read_permission)
) -> List[NetworkResponse]:
    try:
        redes_detalhes = rede_service.obter_detalhes_todas_redes()
        
        redes_response = []
        for rede in redes_detalhes:
            if 'erro' not in rede:
                redes_response.append(NetworkResponse(
                    id=rede['id'],
                    nome=rede['nome'],
                    descricao="",  # Não temos descrição nos detalhes
                    total_nodes=rede['total_nodes'],
                    total_edges=rede['total_edges'],
                    created_at=rede.get('created_at', 0)
                ))
        
        return redes_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar redes: {str(e)}"
        )

@router.get(
    "/{rede_id}/info",
    response_model=NetworkInfoResponse,
    summary="Obter informações da rede",
    description="Obtém informações detalhadas de uma rede específica"
)
async def obter_info_rede(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_read_permission)
) -> NetworkInfoResponse:
    try:
        info = rede_service.obter_info_rede(rede_id)
        
        return NetworkInfoResponse(
            nome=info['nome'],
            total_nodes=info['total_nodes'],
            total_edges=info['total_edges'],
            nodes_tipo=info['nodes_por_tipo'],
            capacidade_total=info['capacidade_total'],
            nodes=info['nodes']
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter informações: {str(e)}"
        )

@router.get(
    "/{rede_id}/validar",
    response_model=StatusResponse,
    summary="Validar integridade da rede",
    description="Verifica se a rede está bem formada e sem problemas"
)
async def validar_rede(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_read_permission)
) -> StatusResponse:
    try:
        resultado = rede_service.validar_rede(rede_id)
        
        status_msg = "valid" if resultado['valida'] else "invalid"
        message = "Rede válida" if resultado['valida'] else f"Rede inválida: {len(resultado['problemas'])} problemas encontrados"
        
        return StatusResponse(
            status=status_msg,
            message=message,
            data=resultado
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na validação: {str(e)}"
        )

@router.post(
    "/{rede_id}/fluxo/preparar",
    response_model=StatusResponse,
    summary="Preparar cálculo de fluxo",
    description="Prepara dados para cálculo de fluxo máximo (Dev 2 pendente)"
)
async def preparar_calculo_fluxo(
    rede_id: str,
    fluxo_data: PrepareFluxRequest,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    try:
        resultado = rede_service.preparar_para_calculo_fluxo(
            rede_id, 
            fluxo_data.origem, 
            fluxo_data.destino
        )
        
        return StatusResponse(
            status="prepared",
            message="Dados preparados para cálculo de fluxo",
            data=resultado
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na preparação: {str(e)}"
        )

@router.get(
    "/{rede_id}/nos",
    response_model=List[Dict[str, str]],
    summary="Listar nós da rede",
    description="Lista todos os nós (depósitos, hubs, zonas) de uma rede"
)
async def listar_nos_rede(
    rede_id: str,
    tipo: str,  # Query parameter opcional para filtrar por tipo
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_read_permission)
) -> List[Dict[str, str]]:
    try:
        info = rede_service.obter_info_rede(rede_id)
        nodes = info.get('nodes', [])
        
        if tipo:
            nodes = [n for n in nodes if n.get('tipo') == tipo]
        
        return nodes
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar nós: {str(e)}"
        )

@router.get(
    "/{rede_id}/estatisticas",
    response_model=StatusResponse,
    summary="Estatísticas da rede",
    description="Retorna estatísticas resumidas da rede"
)
async def obter_estatisticas_rede(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_read_permission)
) -> StatusResponse:
    try:
        info = rede_service.obter_info_rede(rede_id)
        
        estatisticas = {
            "resumo": {
                "nome": info.get('nome'),
                "total_nodes": info.get('total_nodes'),
                "total_edges": info.get('total_edges'),
                "capacidade_total": info.get('capacidade_total')
            },
            "distribuicao": info.get('nodes_por_tipo', {}),
            "metricas": {
                "densidade": info.get('total_edges', 0) / max(1, info.get('total_nodes', 1)),
                "capacidade_media_rota": info.get('capacidade_total', 0) / max(1, info.get('total_edges', 1))
            }
        }
        
        return StatusResponse(
            status="success",
            message="Estatísticas calculadas com sucesso",
            data=estatisticas
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao calcular estatísticas: {str(e)}"
        )