from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from elo import Player, calculate

app = FastAPI(
    title="Contest Elo API",
    description="Stateless Elo rating calculator for weekly coding contests.",
    version="1.0.0",
)


class Participant(BaseModel):
    user_id: str = Field(..., min_length=1)
    current_rating: Optional[float] = Field(
        None, ge=0, description="Rating before this contest. Omit for new users."
    )
    contests_played: int = Field(0, ge=0)
    score: float = Field(..., ge=0, description="Total points earned in the contest")
    penalty: float = Field(0, ge=0, description="Total penalty time; lower is better")


class RatingConfig(BaseModel):
    k_factor: Optional[float] = Field(
        None, gt=0, description="Overrides the automatic K-factor for everyone"
    )
    default_rating: float = Field(1000, ge=0, description="Rating for users with no current_rating")
    scale: float = Field(400, gt=0)
    min_rating: int = Field(0, ge=0, description="Ratings never drop below this")


class ContestRequest(BaseModel):
    contest_id: str = Field(..., min_length=1)
    contest_date: Optional[date] = None
    participants: list[Participant]
    config: RatingConfig = RatingConfig()

    @model_validator(mode="after")
    def check_participants(self):
        if len(self.participants) < 2:
            raise ValueError("At least 2 participants are required.")
        ids = [p.user_id for p in self.participants]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate user_id found in participants.")
        return self


class ParticipantResult(BaseModel):
    user_id: str
    rank: int
    old_rating: int
    new_rating: int
    delta: int
    expected_rank: float
    k_factor_used: float


class ContestResponse(BaseModel):
    contest_id: str
    participant_count: int
    results: list[ParticipantResult]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/calculate", response_model=ContestResponse)
def calculate_ratings(req: ContestRequest):
    cfg = req.config
    players = [
        Player(
            user_id=p.user_id,
            rating=p.current_rating if p.current_rating is not None else cfg.default_rating,
            contests_played=p.contests_played,
            score=p.score,
            penalty=p.penalty,
        )
        for p in req.participants
    ]
    try:
        results = calculate(
            players,
            k_override=cfg.k_factor,
            scale=cfg.scale,
            min_rating=cfg.min_rating,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ContestResponse(
        contest_id=req.contest_id,
        participant_count=len(results),
        results=[ParticipantResult(**r.__dict__) for r in results],
    )
