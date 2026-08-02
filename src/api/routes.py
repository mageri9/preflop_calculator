from fastapi import APIRouter, Depends
import redis.asyncio as aioredis

from src.api.auth import get_current_user_id
from src.api.schemas import (
    DecisionResponse,
    MultiwayDecisionRequest,
    PostflopDecisionRequest,
    PreflopDecisionRequest,
    SessionResponse,
    TableSizeRequest,
    UpdateSessionRequest,
)
from src.core.config import settings
from src.db.base import SessionLocal
from src.engine.decision_engine import DecisionEngine
from src.engine.multiway_resolver import ActionEvent
from src.services.session_manager import SessionManager

router = APIRouter(prefix="/api")
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
session_manager = SessionManager(redis_client)
decision_engine = DecisionEngine()

def _response(session):
    with SessionLocal() as db:
        return SessionResponse.model_validate({
            **session.model_dump(),
            "hero_position_label": session_manager.get_hero_position_label(session, db),
            "stack_bb": session_manager.get_stack_bb(session, db),
        })

@router.get("/session", response_model=SessionResponse)
async def get_session(user_id: int = Depends(get_current_user_id)):
    return _response(await session_manager.get_or_create_session(user_id))

@router.post("/session/next-hand", response_model=SessionResponse)
async def next_hand(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        session = await session_manager.next_hand(user_id, db_session=db)
        return _response(session)

@router.post("/session/table-size", response_model=SessionResponse)
async def table_size(body: TableSizeRequest, user_id: int = Depends(get_current_user_id)):
    return _response(await session_manager.change_table_size(user_id, body.table_size))

@router.post("/session/update", response_model=SessionResponse)
async def update_session(body: UpdateSessionRequest, user_id: int = Depends(get_current_user_id)):
    session = await session_manager.get_or_create_session(user_id)
    payload = body.model_dump(exclude_none=True)

    # Если с фронтенда пришел stack_bb, пересчитываем stack_chips для текущего уровня блайндов
    if "stack_bb" in payload:
        target_bb = payload.pop("stack_bb")
        with SessionLocal() as db:
            structure = session_manager._get_blind_structure_row(session, db)
            bb_chips = structure.bb_chips if structure is not None else 100
            session.stack_chips = max(1, round(target_bb * bb_chips))

    for key, value in payload.items():
        setattr(session, key, value)

    await session_manager.save_session(session)
    return _response(session)

@router.post("/decision/preflop", response_model=DecisionResponse)
async def preflop(body: PreflopDecisionRequest, user_id: int = Depends(get_current_user_id)):
    session = await session_manager.get_or_create_session(user_id)
    with SessionLocal() as db:
        label = session_manager.get_hero_position_label(session, db)
        stack = session_manager.get_stack_bb(session, db)
        if body.facing_action:
            result = decision_engine.get_preflop_facing_action_decision(
                session=db,
                hero_position=label,
                villain_position=body.villain_position,
                villain_action=body.facing_action,
                stack_bb=stack,
                opponent_style=session.opponent_style,
                hero_combo=body.hero_combo,
                table_size=session.table_size,
                icm_stage=session.icm_stage,
                has_ante=session.has_ante,
            )
        else:
            result = decision_engine.get_preflop_first_in_decision(
                session=db,
                table_size=session.table_size,
                hero_position=label,
                stack_bb=stack,
                hero_combo=body.hero_combo,
                icm_stage=session.icm_stage,
                has_ante=session.has_ante,
                opponent_style=session.opponent_style,
            )
    return result

@router.post("/decision/postflop", response_model=DecisionResponse)
async def postflop(body: PostflopDecisionRequest, user_id: int = Depends(get_current_user_id)):
    session = await session_manager.get_or_create_session(user_id)
    with SessionLocal() as db:
        result = decision_engine.get_postflop_decision(
            db, body.hero_cards, body.flop_cards, body.pot_type, body.hero_role, body.hero_position, session_manager.get_stack_bb(session, db)
        )
    return result


@router.post("/decision/multiway", response_model=DecisionResponse)
async def multiway(body: MultiwayDecisionRequest, user_id: int = Depends(get_current_user_id)):
    table_session = await session_manager.get_or_create_session(user_id)
    with SessionLocal() as db:
        result = decision_engine.get_preflop_multiway_decision(
            session=db,
            hero_position=session_manager.get_hero_position_label(table_session, db),
            action_sequence=[ActionEvent(event.position, event.action) for event in body.action_sequence],
            stack_bb=session_manager.get_stack_bb(table_session, db),
            table_size=table_session.table_size,
            icm_stage=table_session.icm_stage,
            has_ante=table_session.has_ante,
            opponent_style=table_session.opponent_style,
            hero_combo=body.hero_combo,
        )
    return result

@router.post("/session/reset", response_model=SessionResponse)
async def reset_session(user_id: int = Depends(get_current_user_id)):
    return _response(await session_manager.reset_session(user_id))
