from fastapi import APIRouter, Depends, HTTPException, status, Query
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

from src.core.entities.models import PrioridadeCliente
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

# Alias para compatibilidade com frontend
@router.post(
    "/gerar-rede-maceio",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Alias para criar rede de Maceió (compatibilidade frontend)",
)
async def gerar_rede_maceio_alias(
    num_clientes: int = 50,
    num_entregadores: Optional[int] = None,
    nome_rede: Optional[str] = None,
    rede_service: RedeService = Depends(get_rede_service)
) -> StatusResponse:
    # Chama a função principal sem autenticação para simplicidade
    try:
        rede_id = rede_service.criar_rede_maceio_completo(
            num_clientes=num_clientes,
            num_entregadores=num_entregadores,
            nome_rede=nome_rede
        )
        
        return StatusResponse(
            status="success",
            message=f"Rede de Maceió gerada com {num_clientes} clientes",
            data={"rede_id": rede_id}
        )
    except Exception as e:
        import traceback
        print("\n❌ Traceback completo ao gerar rede de Maceió:")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar rede de Maceió: {str(e)}"
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
            nodes=info['nodes'],
            edges=info['edges']
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
    summary="Calcular fluxo máximo na rede",
    description="Calcula o fluxo máximo entre dois nós usando algoritmos Ford-Fulkerson e Edmonds-Karp"
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
        
        status_msg = "success" if resultado.get('status') == 'sucesso' else "prepared"
        message = "Fluxo máximo calculado com sucesso" if resultado.get('status') == 'sucesso' else "Erro no cálculo de fluxo"
        
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
            detail=f"Erro no cálculo: {str(e)}"
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

# Rota simples para obter dados da rede (sem autenticação para frontend)
@router.get(
    "/{rede_id}",
    summary="Obter dados completos da rede",
    description="Obtém todos os dados da rede incluindo depósitos, hubs, clientes e veículos"
)
async def obter_rede_completa(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service)
):
    try:
        info = rede_service.obter_info_rede(rede_id)
        
        # Organizar dados por tipo
        depositos = []
        hubs = []
        clientes = []
        
        for node in info.get('nodes', []):
            if node.get('tipo') == 'deposito':
                depositos.append({
                    'id': node['id'],
                    'nome': node.get('nome', f"Depósito {node['id']}"),
                    'latitude': node['latitude'],
                    'longitude': node['longitude'],
                    'capacidade_maxima': node.get('capacidade', 1000),
                    'endereco': node.get('endereco', 'Endereço não informado')
                })
            elif node.get('tipo') == 'hub':
                hubs.append({
                    'id': node['id'],
                    'nome': node.get('nome', f"Hub {node['id']}"),
                    'latitude': node['latitude'],
                    'longitude': node['longitude'],
                    'capacidade': node.get('capacidade', 500),
                    'endereco': node.get('endereco', 'Endereço não informado')
                })
            elif node.get('tipo') == 'cliente':
                clientes.append({
                    'id': node['id'],
                    'latitude': node['latitude'],
                    'longitude': node['longitude'],
                    'demanda_media': node.get('demanda'),
                    'prioridade': node.get('prioridade', 'normal'),
                    'zona_id': node.get('zona_id', 1)
                })
        
        return {
            'id': rede_id,
            'nome': info.get('nome', f'Rede {rede_id}'),
            'depositos': depositos,
            'hubs': hubs,
            'clientes': clientes,
            'total_nodes': info.get('total_nodes', 0),
            'total_edges': info.get('total_edges', 0)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter dados da rede: {str(e)}"
        )

# Rotas para controle de movimento dos veículos
@router.post(
    "/{rede_id}/start-movement",
    summary="Iniciar movimento de veículos",
    description="Inicia o movimento automático dos veículos na rede"
)
async def start_vehicle_movement(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service)
):
    try:
        # Verificar se a rede existe
        info = rede_service.obter_info_rede(rede_id)
        
        # Iniciar movimento usando o serviço
        success = rede_service.start_vehicle_movement(rede_id)
        
        if success:
            return {
                "status": "success",
                "message": f"Movimento iniciado para rede {rede_id}",
                "rede_id": rede_id
            }
        else:
            return {
                "status": "error",
                "message": f"Falha ao iniciar movimento para rede {rede_id}",
                "rede_id": rede_id
            }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao iniciar movimento: {str(e)}"
        )

@router.post(
    "/{rede_id}/stop-movement",
    summary="Parar movimento de veículos",
    description="Para o movimento automático dos veículos na rede"
)
async def stop_vehicle_movement(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service)
):
    try:
        # Verificar se a rede existe
        info = rede_service.obter_info_rede(rede_id)
        
        # Parar movimento usando o serviço
        success = rede_service.stop_vehicle_movement()
        
        if success:
            return {
                "status": "success",
                "message": f"Movimento parado para rede {rede_id}",
                "rede_id": rede_id
            }
        else:
            return {
                "status": "error",
                "message": f"Falha ao parar movimento para rede {rede_id}",
                "rede_id": rede_id
            }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao parar movimento: {str(e)}"
        )

@router.get(
    "/{rede_id}/delivery-stats",
    summary="Obter estatísticas de entrega",
    description="Retorna estatísticas detalhadas das entregas realizadas"
)
async def get_delivery_statistics(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service)
):
    try:
        # Verificar se a rede existe
        info = rede_service.obter_info_rede(rede_id)
        
        # Obter estatísticas de movimento
        stats = rede_service.get_movement_statistics()
        
        return {
            "status": "success",
            "rede_id": rede_id,
            "statistics": stats
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter estatísticas: {str(e)}"
        )

@router.post(
    "/{rede_id}/reset-deliveries",
    summary="Resetar sistema de entregas",
    description="Reseta o sistema de entregas para reiniciar o ciclo"
)
async def reset_delivery_system(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service)
):
    try:
        # Verificar se a rede existe
        info = rede_service.obter_info_rede(rede_id)
        
        return {
            "status": "success",
            "message": f"Sistema de entregas resetado para rede {rede_id}",
            "rede_id": rede_id
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao resetar entregas: {str(e)}"
        )

@router.post(
    "/{rede_id}/bloquear-rota",
    response_model=StatusResponse,
    summary="Bloquear rota entre dois nós",
    description="Simula o bloqueio de uma rota (aresta) entre dois nós da rede."
)
async def bloquear_rota(
    rede_id: str,
    origem_id: str = Query(..., description="ID do nó de origem"),
    destino_id: str = Query(..., description="ID do nó de destino"),
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    if not rede_service.bloquear_rota(rede_id, origem_id, destino_id):
        raise HTTPException(status_code=404, detail="Rota não encontrada ou já bloqueada")
    return StatusResponse(
        status="success",
        message=f"Rota {origem_id} -> {destino_id} bloqueada com sucesso"
    )

@router.post(
    "/{rede_id}/desbloquear-rota",
    response_model=StatusResponse,
    summary="Desbloquear rota entre dois nós",
    description="Desbloqueia (adiciona) uma rota entre dois nós da rede."
)
async def desbloquear_rota(
    rede_id: str,
    origem_id: str = Query(..., description="ID do nó de origem"),
    destino_id: str = Query(..., description="ID do nó de destino"),
    peso: float = Query(1.0, description="Peso da rota"),
    capacidade: int = Query(1, description="Capacidade da rota"),
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    if not rede_service.desbloquear_rota(rede_id, origem_id, destino_id, peso, capacidade):
        raise HTTPException(status_code=400, detail="Rota já existe ou não pode ser desbloqueada")
    return StatusResponse(
        status="success",
        message=f"Rota {origem_id} -> {destino_id} desbloqueada com sucesso"
    )

@router.post(
    "/{rede_id}/aumentar-demanda-zona",
    response_model=StatusResponse,
    summary="Aumentar demanda em uma zona",
    description="Aumenta a demanda de todos os clientes de uma zona específica."
)
async def aumentar_demanda_zona(
    rede_id: str,
    zona_id: str = Query(..., description="ID da zona"),
    fator: float = Query(2.0, description="Fator multiplicador da demanda"),
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
) -> StatusResponse:
    afetados = rede_service.aumentar_demanda_zona(rede_id, zona_id, fator)
    if afetados == 0:
        raise HTTPException(status_code=404, detail="Zona não encontrada ou sem clientes")
    return StatusResponse(
        status="success",
        message=f"Demanda aumentada em {afetados} clientes da zona {zona_id}"
    )

@router.post("/{rede_id}/alterar-prioridade-cliente")
async def alterar_prioridade_cliente(
    rede_id: str,
    cliente_id: str = Query(..., description="ID do cliente"),
    prioridade: int = Query(..., description="Prioridade (1=URGENTE, 2=ALTA, 3=NORMAL, 4=BAIXA)"),
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_write_permission)
):
    if rede_id not in rede_service.redes_cache:
        raise HTTPException(status_code=404, detail="Rede não encontrada")
    rede = rede_service.redes_cache[rede_id]
    for cliente in rede.clientes:
        if cliente.id == cliente_id:
            cliente.prioridade = PrioridadeCliente(prioridade)
            return {"status": "ok", "mensagem": f"Prioridade do cliente {cliente_id} alterada para {PrioridadeCliente(prioridade).name}"}
    raise HTTPException(status_code=404, detail="Cliente não encontrado")

@router.get("/{rede_id}/relatorio-operacional", summary="Relatório de gargalos e capacidade ociosa")
async def relatorio_operacional(
    rede_id: str,
    rede_service: RedeService = Depends(get_rede_service),
    current_user: User = Depends(require_read_permission)
):
    if rede_id not in rede_service.redes_cache:
        raise HTTPException(status_code=404, detail="Rede não encontrada")
    rede = rede_service.redes_cache[rede_id]

    gargalos = []
    ociosos = []

    # Exemplo: gargalo = rotas com uso > 90% da capacidade
    for rota in getattr(rede, "rotas", []):
        if hasattr(rota, "uso_atual") and hasattr(rota, "capacidade"):
            if rota.capacidade > 0:
                uso = rota.uso_atual / rota.capacidade
                if uso > 0.9:
                    gargalos.append({
                        "origem": rota.origem,
                        "destino": rota.destino,
                        "uso_percentual": round(uso * 100, 1)
                    })
                elif uso < 0.2:
                    ociosos.append({
                        "origem": rota.origem,
                        "destino": rota.destino,
                        "uso_percentual": round(uso * 100, 1)
                    })

    return {
        "gargalos": gargalos,
        "capacidade_ociosa": ociosos,
        "total_rotas": len(getattr(rede, "rotas", []))
    }

