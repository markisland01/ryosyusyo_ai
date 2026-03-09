from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.rule import Rule
from app.schemas.rule import RuleCreate, RuleListResponse, RuleResponse, RuleUpdate

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("/", response_model=RuleListResponse)
async def list_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Rule).order_by(Rule.rule_type.asc(), Rule.priority.asc(), Rule.id.asc())
    )
    rules = list(result.scalars().all())
    return RuleListResponse(rules=rules, total=len(rules))


@router.post("/", response_model=RuleResponse)
async def create_rule(payload: RuleCreate, db: AsyncSession = Depends(get_db)):
    rule = Rule(**payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: int, payload: RuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="ルールが見つかりません")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="ルールが見つかりません")

    await db.delete(rule)
    await db.commit()
    return {"deleted": rule_id}
