"""Business rules. No web code here, so every rule can be unit-tested."""

import re
from datetime import date, timedelta
from math import ceil

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import MenuEntry, Plan, PriceItem, Recipe, RecipeIngredient, User, Wallet
from .security import hash_password, verify_password

PERIOD_DAYS = {"day": 1, "week": 7, "month": 30}
SLOTS = ("lunch", "dinner")
MIN_SERVINGS, STEP = 0.5, 0.25
RECENT = 3  # a recipe is not repeated within this many meals if avoidable
USERNAME = re.compile(r"[A-Za-z0-9_]{3,30}")
MIN_PASSWORD, MAX_PASSWORD = 8, 128


# ---------- accounts ----------

# Checked when the username does not exist, so a failed login takes as long as a real one.
_NO_USER_HASH = hash_password("no-such-user")


def find_user(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))


def register_user(db: Session, username: str, password: str, confirm: str) -> User:
    username = username.strip()
    if not USERNAME.fullmatch(username):
        raise ValueError("Tên đăng nhập chỉ gồm chữ không dấu, số và dấu gạch dưới, từ 3 đến 30 ký tự")
    if len(password) < MIN_PASSWORD:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")
    if len(password) > MAX_PASSWORD:
        raise ValueError("Mật khẩu quá dài, tối đa 128 ký tự")
    if password != confirm:
        raise ValueError("Mật khẩu nhập lại không khớp")
    if find_user(db, username) is not None:
        raise ValueError("Tên đăng nhập này đã có người dùng")
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = find_user(db, username)
    stored = user.password_hash if user is not None else _NO_USER_HASH
    if verify_password(password, stored) and user is not None:
        return user
    raise ValueError("Sai tên đăng nhập hoặc mật khẩu")


# ---------- wallet (one per user) ----------

def get_wallet(db: Session, user: User) -> Wallet:
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user.id))
    if wallet is None:
        wallet = Wallet(user_id=user.id, balance=0)
        db.add(wallet)
        db.flush()
    return wallet


def topup(db: Session, user: User, amount: int) -> Wallet:
    if amount <= 0:
        raise ValueError("Số tiền nạp phải lớn hơn 0")
    wallet = get_wallet(db, user)
    wallet.balance += amount
    return wallet


# ---------- costs and exclusions ----------

def cost_per_serving(recipe: Recipe) -> int:
    total = sum(ri.quantity * ri.item.price for ri in recipe.ingredients)
    return round(total / recipe.servings)


def entry_cost(entry: MenuEntry) -> float:
    return cost_per_serving(entry.recipe) * entry.servings


def excluded_words(text: str) -> list[str]:
    return [w.strip().lower() for w in text.split(",") if w.strip()]


def is_excluded(recipe: Recipe, words: list[str]) -> bool:
    return any(w in ri.item.name.lower() for w in words for ri in recipe.ingredients)


def eligible_recipes(db: Session, plan: Plan) -> list[Recipe]:
    words = excluded_words(plan.exclusions)
    return [r for r in db.scalars(select(Recipe)) if not is_excluded(r, words)]


def entries(db: Session, plan: Plan) -> list[MenuEntry]:
    return list(
        db.scalars(
            select(MenuEntry)
            .where(MenuEntry.plan_id == plan.id)
            .order_by(MenuEntry.day, MenuEntry.slot.desc())  # lunch before dinner
        )
    )


def plan_cost(db: Session, plan: Plan) -> int:
    """Always priced with today's catalog, so a price change shows up immediately."""
    return round(sum(entry_cost(e) for e in entries(db, plan)))


def plan_end(plan: Plan) -> date:
    return plan.start_date + timedelta(days=PERIOD_DAYS[plan.period] - 1)


# ---------- menu generation ----------

def generate_menu(db: Session, plan: Plan, from_day: date) -> None:
    """(Re)build every meal from `from_day` on; earlier days are kept as eaten."""
    end = plan_end(plan)
    if from_day > end:
        raise ValueError("Kế hoạch này đã kết thúc")
    from_day = max(from_day, plan.start_date)
    recipes = eligible_recipes(db, plan)
    if not recipes:
        raise ValueError("Không có món nào phù hợp với danh sách thực phẩm cần tránh")

    db.execute(delete(MenuEntry).where(MenuEntry.plan_id == plan.id, MenuEntry.day >= from_day))
    db.flush()
    left = plan.budget - sum(entry_cost(e) for e in entries(db, plan))

    by_cost = sorted(recipes, key=cost_per_serving)
    slots = [
        (from_day + timedelta(days=d), s)
        for d in range((end - from_day).days + 1)
        for s in SLOTS
    ]
    recent: list[int] = []
    for i, (day, slot) in enumerate(slots):
        cap = left / (len(slots) - i)
        affordable = [r for r in by_cost if cost_per_serving(r) <= cap]
        pool = [r for r in affordable if r.id not in recent] or affordable
        pick = pool[-1] if pool else by_cost[0]  # priciest that fits, else the cheapest
        left -= cost_per_serving(pick)
        recent = (recent + [pick.id])[-RECENT:]
        db.add(MenuEntry(plan_id=plan.id, day=day, slot=slot, recipe_id=pick.id, servings=1.0))
    db.flush()


def create_plan(db: Session, user: User, period: str, budget: int, start: date, exclusions: str) -> Plan:
    if period not in PERIOD_DAYS:
        raise ValueError("Chu kỳ phải là ngày, tuần hoặc tháng")
    if budget <= 0:
        raise ValueError("Ngân sách phải lớn hơn 0")
    wallet = get_wallet(db, user)
    if budget > wallet.balance:
        raise ValueError("Số dư ví không đủ, hãy nạp thêm tiền")
    wallet.balance -= budget
    plan = Plan(user_id=user.id, period=period, start_date=start, budget=budget, exclusions=exclusions.strip())
    db.add(plan)
    db.flush()
    generate_menu(db, plan, start)
    return plan


def upgrade_plan(db: Session, user: User, plan: Plan, amount: int, today: date) -> None:
    """Move `amount` from the user's wallet into the plan and rebuild the days still to come."""
    wallet = get_wallet(db, user)
    if amount <= 0 or amount > wallet.balance:
        raise ValueError("Số tiền nâng cấp không hợp lệ hoặc vượt số dư ví")
    wallet.balance -= amount
    plan.budget += amount
    generate_menu(db, plan, today)


# ---------- over-budget fixes (the user picks one, the app never swaps silently) ----------

def _editable(db: Session, plan: Plan, today: date) -> list[MenuEntry]:
    return [e for e in entries(db, plan) if e.day >= today]


def fix_cheaper(db: Session, plan: Plan, today: date) -> bool:
    recipes = eligible_recipes(db, plan)
    while plan_cost(db, plan) > plan.budget:
        for e in sorted(_editable(db, plan, today), key=entry_cost, reverse=True):
            cheaper = [r for r in recipes if cost_per_serving(r) < cost_per_serving(e.recipe)]
            if cheaper:
                e.recipe = max(cheaper, key=cost_per_serving)  # smallest step down
                db.flush()
                break
        else:
            break
    return plan_cost(db, plan) <= plan.budget


def fix_smaller(db: Session, plan: Plan, today: date) -> bool:
    while plan_cost(db, plan) > plan.budget:
        shrinkable = [e for e in _editable(db, plan, today) if e.servings > MIN_SERVINGS]
        if not shrinkable:
            break
        max(shrinkable, key=entry_cost).servings -= STEP
        db.flush()
    return plan_cost(db, plan) <= plan.budget


# ---------- shopping list ----------

def week_count(plan: Plan) -> int:
    return ceil(PERIOD_DAYS[plan.period] / 7)


def shopping_list(db: Session, plan: Plan, week: int | None = None):
    """Rows of (item, quantity, cost) summed over the plan, or over one 1-based week."""
    qty: dict[int, float] = {}
    items: dict[int, PriceItem] = {}
    for e in entries(db, plan):
        if week is not None and (e.day - plan.start_date).days // 7 + 1 != week:
            continue
        for ri in e.recipe.ingredients:
            items[ri.item_id] = ri.item
            qty[ri.item_id] = qty.get(ri.item_id, 0) + ri.quantity / e.recipe.servings * e.servings
    rows = sorted(
        ((items[i], round(q, 2), round(q * items[i].price)) for i, q in qty.items()),
        key=lambda r: r[0].name,
    )
    return rows, sum(r[2] for r in rows)


# ---------- recipes and prices ----------

def parse_ingredients(db: Session, text: str) -> list[tuple[PriceItem, float]]:
    """One ingredient per line as `name; quantity`, name must exist in the price list."""
    parsed = []
    for line in filter(None, (raw_line.strip() for raw_line in text.splitlines())):
        name, _, raw = line.partition(";")
        item = db.scalar(select(PriceItem).where(func.lower(PriceItem.name) == name.strip().lower()))
        if item is None:
            raise ValueError(f"Không tìm thấy nguyên liệu '{name.strip()}' trong bảng giá")
        try:
            quantity = float(raw.replace(",", "."))
        except ValueError:
            raise ValueError(f"Số lượng của '{item.name}' không hợp lệ") from None
        if quantity <= 0:
            raise ValueError(f"Số lượng của '{item.name}' phải lớn hơn 0")
        parsed.append((item, quantity))
    if not parsed:
        raise ValueError("Món ăn cần ít nhất một nguyên liệu")
    return parsed


def save_recipe(db: Session, recipe: Recipe | None, name: str, servings: float, text: str) -> Recipe:
    name = name.strip()
    if not name:
        raise ValueError("Tên món không được để trống")
    if servings <= 0:
        raise ValueError("Số khẩu phần phải lớn hơn 0")
    clash = db.scalar(select(Recipe).where(func.lower(Recipe.name) == name.lower()))
    if clash and (recipe is None or clash.id != recipe.id):
        raise ValueError("Đã có món trùng tên")
    parsed = parse_ingredients(db, text)
    if recipe is None:
        recipe = Recipe()
        db.add(recipe)
    recipe.name, recipe.servings = name, servings
    recipe.ingredients = [RecipeIngredient(item=i, quantity=q) for i, q in parsed]
    db.flush()
    return recipe


def delete_recipe(db: Session, recipe: Recipe) -> None:
    if db.scalar(select(func.count()).select_from(MenuEntry).where(MenuEntry.recipe_id == recipe.id)):
        raise ValueError("Món đang nằm trong thực đơn, không xoá được")
    db.delete(recipe)


def add_price(db: Session, name: str, unit: str, price: int, category: str) -> PriceItem:
    name, unit = name.strip(), unit.strip()
    if not name or not unit:
        raise ValueError("Tên và đơn vị không được để trống")
    if price <= 0:
        raise ValueError("Giá phải lớn hơn 0")
    if db.scalar(select(PriceItem).where(func.lower(PriceItem.name) == name.lower())):
        raise ValueError("Đã có sản phẩm trùng tên")
    item = PriceItem(name=name, unit=unit, price=price, category=category.strip())
    db.add(item)
    db.flush()
    return item


def update_price(item: PriceItem, unit: str, price: int) -> None:
    if price <= 0 or not unit.strip():
        raise ValueError("Giá phải lớn hơn 0 và đơn vị không được để trống")
    item.unit, item.price = unit.strip(), price


def delete_price(db: Session, item: PriceItem) -> None:
    if db.scalar(select(func.count()).select_from(RecipeIngredient).where(RecipeIngredient.item_id == item.id)):
        raise ValueError("Sản phẩm đang dùng trong công thức, không xoá được")
    db.delete(item)
