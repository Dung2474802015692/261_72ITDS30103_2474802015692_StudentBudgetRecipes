from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import services as sv
from app.models import PriceItem, Recipe
from app.seed import ITEMS

TODAY = date(2026, 11, 2)


def make_plan(db, period="week", budget=300_000, exclusions=""):
    sv.topup(db, budget)
    return sv.create_plan(db, period, budget, TODAY, exclusions)


def test_seed_has_at_least_100_items_and_recipes_resolve(db):
    assert len(ITEMS.strip().splitlines()) >= 100
    assert db.scalars(select(Recipe)).first() is not None


def test_topup_rejects_non_positive(db):
    with pytest.raises(ValueError):
        sv.topup(db, 0)


def test_create_plan_takes_budget_from_wallet(db):
    sv.topup(db, 500_000)
    sv.create_plan(db, "week", 300_000, TODAY, "")
    assert sv.get_wallet(db).balance == 200_000


def test_create_plan_refuses_more_than_wallet(db):
    sv.topup(db, 100_000)
    with pytest.raises(ValueError):
        sv.create_plan(db, "week", 300_000, TODAY, "")


@pytest.mark.parametrize("period,meals", [("day", 2), ("week", 14), ("month", 60)])
def test_menu_has_two_meals_per_day(db, period, meals):
    plan = make_plan(db, period, 100_000 * meals // 2)
    assert len(sv.entries(db, plan)) == meals


def test_generated_menu_fits_budget(db):
    plan = make_plan(db, "week", 300_000)
    assert sv.plan_cost(db, plan) <= plan.budget


def test_exclusions_are_never_used(db):
    plan = make_plan(db, "week", 300_000, "trứng, tôm")
    for e in sv.entries(db, plan):
        assert not sv.is_excluded(e.recipe, ["trứng", "tôm"])


def test_everything_excluded_is_refused(db):
    sv.topup(db, 100_000)
    with pytest.raises(ValueError):
        sv.create_plan(db, "day", 50_000, TODAY, "gạo, mì gói, bún, miến, bánh mì")


def test_price_rise_pushes_plan_over_budget_and_cheaper_fixes_it(db):
    plan = make_plan(db, "week", 300_000)
    for item in db.scalars(select(PriceItem)):
        item.price = round(item.price * 1.15)
    db.flush()
    assert sv.plan_cost(db, plan) > plan.budget
    assert sv.fix_cheaper(db, plan, TODAY) is True
    assert sv.plan_cost(db, plan) <= plan.budget


def test_smaller_portions_fix_overrun(db):
    plan = make_plan(db, "week", 300_000)
    for item in db.scalars(select(PriceItem)):
        item.price = round(item.price * 1.1)
    db.flush()
    assert sv.fix_smaller(db, plan, TODAY) is True
    assert sv.plan_cost(db, plan) <= plan.budget
    assert min(e.servings for e in sv.entries(db, plan)) >= sv.MIN_SERVINGS


def test_fixes_leave_past_days_alone(db):
    plan = make_plan(db, "week", 300_000)
    for item in db.scalars(select(PriceItem)):
        item.price *= 2
    db.flush()
    before = [(e.recipe_id, e.servings) for e in sv.entries(db, plan) if e.day < TODAY + timedelta(days=3)]
    sv.fix_smaller(db, plan, TODAY + timedelta(days=3))
    after = [(e.recipe_id, e.servings) for e in sv.entries(db, plan) if e.day < TODAY + timedelta(days=3)]
    assert before == after


def test_upgrade_keeps_past_days_and_spends_extra(db):
    plan = make_plan(db, "week", 200_000)
    today = TODAY + timedelta(days=3)
    past = [(e.day, e.slot, e.recipe_id) for e in sv.entries(db, plan) if e.day < today]
    cost_before = sv.plan_cost(db, plan)
    sv.topup(db, 100_000)
    sv.upgrade_plan(db, plan, 100_000, today)
    assert [(e.day, e.slot, e.recipe_id) for e in sv.entries(db, plan) if e.day < today] == past
    assert plan.budget == 300_000
    assert cost_before < sv.plan_cost(db, plan) <= plan.budget
    assert sv.get_wallet(db).balance == 0


def test_upgrade_cannot_exceed_wallet(db):
    plan = make_plan(db, "week", 200_000)
    with pytest.raises(ValueError):
        sv.upgrade_plan(db, plan, 1, TODAY)


def test_shopping_list_total_matches_item_costs_and_week_filter(db):
    plan = make_plan(db, "month", 1_200_000)
    rows, total = sv.shopping_list(db, plan)
    assert total == sum(r[2] for r in rows)
    week1, _ = sv.shopping_list(db, plan, week=1)
    assert 0 < len(week1) <= len(rows)
    assert sv.week_count(plan) == 5


def test_recipe_rejects_unknown_ingredient_and_bad_quantity(db):
    with pytest.raises(ValueError):
        sv.save_recipe(db, None, "Món thử", 1, "kim cương; 1")
    with pytest.raises(ValueError):
        sv.save_recipe(db, None, "Món thử", 1, "gạo; abc")
    with pytest.raises(ValueError):
        sv.save_recipe(db, None, "Món thử", 1, "gạo; -1")


def test_recipe_in_menu_cannot_be_deleted(db):
    plan = make_plan(db, "day", 100_000)
    used = sv.entries(db, plan)[0].recipe
    with pytest.raises(ValueError):
        sv.delete_recipe(db, used)


def test_price_in_recipe_cannot_be_deleted(db):
    rice = db.scalar(select(PriceItem).where(PriceItem.name == "gạo"))
    with pytest.raises(ValueError):
        sv.delete_price(db, rice)
