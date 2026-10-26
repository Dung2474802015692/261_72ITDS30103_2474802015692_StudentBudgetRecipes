from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ai
from . import services as sv
from .db import Base, SessionLocal, engine, get_db
from .models import Plan, PriceItem, Recipe
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Student Budget Recipes", lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["vnd"] = lambda n: f"{round(n):,}".replace(",", ".") + "đ"


def page(request: Request, name: str, **ctx):
    ctx["error"] = request.query_params.get("error")
    return templates.TemplateResponse(request, name, ctx)


def go(url: str, error: str | None = None):
    if error:
        url += ("&" if "?" in url else "?") + "error=" + quote(error)
    return RedirectResponse(url, status_code=303)


def get_or_404(db: Session, model, id: int):
    obj = db.get(model, id)
    if obj is None:
        raise HTTPException(404)
    return obj


def run(db: Session, ok_url: str, fail_url: str, action):
    """Commit `action` on success; roll everything back and show the message on a rule violation."""
    try:
        action()
        db.commit()
    except ValueError as exc:
        db.rollback()
        return go(fail_url, str(exc))
    return go(ok_url)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- wallet and plans ----------

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    plans = db.scalars(select(Plan).order_by(Plan.id.desc())).all()
    rows = [(p, sv.plan_cost(db, p), sv.plan_end(p)) for p in plans]
    return page(request, "home.html", wallet=sv.get_wallet(db), rows=rows, today=date.today())


@app.post("/wallet/topup")
def wallet_topup(amount: int = Form(...), db: Session = Depends(get_db)):
    return run(db, "/", "/", lambda: sv.topup(db, amount))


@app.post("/plans")
def plans_create(
    period: str = Form(...),
    budget: int = Form(...),
    start: date = Form(...),
    exclusions: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        plan = sv.create_plan(db, period, budget, start, exclusions)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return go("/", str(exc))
    return go(f"/plans/{plan.id}")


@app.get("/plans/{plan_id}")
def plan_detail(plan_id: int, request: Request, db: Session = Depends(get_db)):
    plan = get_or_404(db, Plan, plan_id)
    days: dict[date, dict] = {}
    for e in sv.entries(db, plan):
        days.setdefault(e.day, {})[e.slot] = e
    cost = sv.plan_cost(db, plan)
    offer = request.query_params.get("offer")
    return page(
        request, "plan.html",
        plan=plan, days=days, cost=cost, over=cost > plan.budget, weeks=sv.week_count(plan),
        wallet=sv.get_wallet(db), offer=int(offer) if offer and offer.isdigit() else None,
        costs=sv.cost_per_serving,
    )


@app.post("/plans/{plan_id}/cheaper")
def plan_cheaper(plan_id: int, db: Session = Depends(get_db)):
    plan = get_or_404(db, Plan, plan_id)
    fits = sv.fix_cheaper(db, plan, date.today())
    db.commit()
    return go(f"/plans/{plan_id}", None if fits else "Đã thay món rẻ hơn nhưng vẫn vượt ngân sách")


@app.post("/plans/{plan_id}/smaller")
def plan_smaller(plan_id: int, db: Session = Depends(get_db)):
    plan = get_or_404(db, Plan, plan_id)
    fits = sv.fix_smaller(db, plan, date.today())
    db.commit()
    return go(f"/plans/{plan_id}", None if fits else "Đã giảm khẩu phần nhưng vẫn vượt ngân sách")


@app.post("/plans/{plan_id}/topup")
def plan_topup(plan_id: int, amount: int = Form(...), db: Session = Depends(get_db)):
    get_or_404(db, Plan, plan_id)
    return run(db, f"/plans/{plan_id}?offer={amount}", f"/plans/{plan_id}", lambda: sv.topup(db, amount))


@app.post("/plans/{plan_id}/upgrade")
def plan_upgrade(plan_id: int, amount: int = Form(...), db: Session = Depends(get_db)):
    plan = get_or_404(db, Plan, plan_id)
    return run(db, f"/plans/{plan_id}", f"/plans/{plan_id}", lambda: sv.upgrade_plan(db, plan, amount, date.today()))


# ---------- shopping list ----------

def shopping_page(request: Request, db: Session, plan_id: int, week: int | None, **extra):
    plan = get_or_404(db, Plan, plan_id)
    rows, total = sv.shopping_list(db, plan, week)
    return page(
        request, "shopping.html",
        plan=plan, rows=rows, total=total, week=week, weeks=sv.week_count(plan), **extra,
    )


@app.get("/shopping/{plan_id}")
def shopping(plan_id: int, request: Request, week: int | None = None, db: Session = Depends(get_db)):
    return shopping_page(request, db, plan_id, week)


@app.post("/shopping/{plan_id}/substitute")
def shopping_substitute(
    plan_id: int, request: Request, item_id: int = Form(...), week: int | None = Form(None),
    db: Session = Depends(get_db),
):
    plan = get_or_404(db, Plan, plan_id)
    item = get_or_404(db, PriceItem, item_id)
    try:
        subs = ai.suggest_substitutes(item.name, sv.excluded_words(plan.exclusions))
    except ai.AIError:
        subs = None  # the page still shows the list and a notice instead
    return shopping_page(request, db, plan_id, week, sub_item=item, subs=subs)


# ---------- price list ----------

@app.get("/prices")
def prices(request: Request, db: Session = Depends(get_db)):
    return page(request, "prices.html", items=db.scalars(select(PriceItem).order_by(PriceItem.category, PriceItem.name)).all())


@app.post("/prices")
def prices_add(
    name: str = Form(...), unit: str = Form(...), price: int = Form(...), category: str = Form(""),
    db: Session = Depends(get_db),
):
    return run(db, "/prices", "/prices", lambda: sv.add_price(db, name, unit, price, category))


@app.post("/prices/{item_id}")
def prices_update(item_id: int, unit: str = Form(...), price: int = Form(...), db: Session = Depends(get_db)):
    item = get_or_404(db, PriceItem, item_id)
    return run(db, "/prices", "/prices", lambda: sv.update_price(item, unit, price))


@app.post("/prices/{item_id}/delete")
def prices_delete(item_id: int, db: Session = Depends(get_db)):
    item = get_or_404(db, PriceItem, item_id)
    return run(db, "/prices", "/prices", lambda: sv.delete_price(db, item))


# ---------- recipes ----------

@app.get("/recipes")
def recipes(request: Request, db: Session = Depends(get_db)):
    return page(request, "recipes.html", recipes=db.scalars(select(Recipe).order_by(Recipe.name)).all(), edit=None, costs=sv.cost_per_serving)


@app.get("/recipes/{recipe_id}/edit")
def recipe_edit(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    recipe = get_or_404(db, Recipe, recipe_id)
    return page(request, "recipes.html", recipes=db.scalars(select(Recipe).order_by(Recipe.name)).all(), edit=recipe, costs=sv.cost_per_serving)


@app.post("/recipes")
def recipe_add(name: str = Form(...), servings: float = Form(1), ingredients: str = Form(""), db: Session = Depends(get_db)):
    return run(db, "/recipes", "/recipes", lambda: sv.save_recipe(db, None, name, servings, ingredients))


@app.post("/recipes/{recipe_id}")
def recipe_update(recipe_id: int, name: str = Form(...), servings: float = Form(1), ingredients: str = Form(""), db: Session = Depends(get_db)):
    recipe = get_or_404(db, Recipe, recipe_id)
    return run(db, "/recipes", f"/recipes/{recipe_id}/edit", lambda: sv.save_recipe(db, recipe, name, servings, ingredients))


@app.post("/recipes/{recipe_id}/delete")
def recipe_delete(recipe_id: int, db: Session = Depends(get_db)):
    recipe = get_or_404(db, Recipe, recipe_id)
    return run(db, "/recipes", "/recipes", lambda: sv.delete_recipe(db, recipe))
