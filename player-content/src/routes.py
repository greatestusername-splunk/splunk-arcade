import os
from typing import Annotated

import requests
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from src.questions import _Questions
from src.walkthroughs import _Walkthroughs

router = APIRouter()

SCOREBOARD_HOST = os.getenv("SCOREBOARD_HOST")


@router.get("/alive")
def alive():
    return JSONResponse(content={"success": True})


@router.get("/quiz/questions/{module}/{question_count}")
async def get_questions(
    module: str, question_count: int, player_name: Annotated[str | None, Header()] = None
) -> JSONResponse:
    seen_questions_resp = requests.get(
        f"http://{SCOREBOARD_HOST}/player_seen_questions/{module}",
        headers={"Player-Name": player_name},
    )
    seen_questions = seen_questions_resp.json()

    q = _Questions()
    return JSONResponse(
        content=q.questions_for_module(
            module=module,
            question_count=question_count,
            seen_questions=seen_questions,
            player_name=player_name,
        )
    )


@router.get("/walkthrough/{module}/{stage}")
async def get_walkthrough(module: str, stage: int) -> JSONResponse:
    w = _Walkthroughs()

    try:
        return JSONResponse(content=w.get_module_stage(module=module, stage=stage))
    except IndexError:
        raise HTTPException(
            status_code=422, detail=f"stage {stage} not present for module {module}"
        )
