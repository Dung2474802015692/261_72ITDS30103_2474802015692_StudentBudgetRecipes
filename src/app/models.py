from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class PriceItem(Base):
    """One supermarket product; `price` is VND per `unit`."""

    __tablename__ = "price_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    unit: Mapped[str]
    price: Mapped[int]
    category: Mapped[str] = mapped_column(default="")


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    servings: Mapped[float] = mapped_column(default=1.0)
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeIngredient(Base):
    """`quantity` is expressed in the PriceItem's own unit, for the recipe's `servings`."""

    __tablename__ = "recipe_ingredient"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("price_item.id"))
    quantity: Mapped[float]
    item: Mapped[PriceItem] = relationship(lazy="selectin")


class User(Base):
    """Someone who signs in. Each user has one wallet and their own plans."""

    __tablename__ = "app_user"  # "user" is a reserved word in PostgreSQL

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]


class Wallet(Base):
    __tablename__ = "wallet"

    id: Mapped[int] = mapped_column(primary_key=True)
    balance: Mapped[int] = mapped_column(default=0)
    # NULL only in rows created before accounts existed; those belong to nobody and stay hidden.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), unique=True, index=True, nullable=True)


class Plan(Base):
    __tablename__ = "plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str]  # day | week | month
    start_date: Mapped[date]
    budget: Mapped[int]
    exclusions: Mapped[str] = mapped_column(default="")  # comma-separated words
    # NULL only in plans created before accounts existed; those belong to nobody and stay hidden.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), index=True, nullable=True)


class MenuEntry(Base):
    __tablename__ = "menu_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    day: Mapped[date]
    slot: Mapped[str]  # lunch | dinner
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"))
    servings: Mapped[float] = mapped_column(default=1.0)
    recipe: Mapped[Recipe] = relationship(lazy="selectin")
