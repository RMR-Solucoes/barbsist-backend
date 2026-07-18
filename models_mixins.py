from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import declared_attr, relationship


class BarbeariaMixin:
    """
    Adiciona o vínculo obrigatório com uma barbearia às entidades
    operacionais do sistema.

    Deve ser utilizado somente em modelos cujos registros pertencem
    diretamente a uma barbearia.

    Exemplo:

        class Cliente(BarbeariaMixin, Base):
            __tablename__ = "clientes"
    """

    @declared_attr
    def barbearia_id(cls):
        return Column(
            Integer,
            ForeignKey(
                "barbearias.id",
                ondelete="RESTRICT"
            ),
            nullable=False,
            index=True
        )

    @declared_attr
    def barbearia(cls):
        return relationship(
            "Barbearia",
            foreign_keys=lambda: [cls.barbearia_id],
            lazy="joined"
        )