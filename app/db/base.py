from datetime import date, datetime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.inspection import inspect
from decimal import Decimal
class ToDictMixin:
    def to_dict(self, include_relationships=False):
        def serialize_value(value):
            if isinstance(value, (datetime, date)):
                return value.isoformat()  # '2025-08-26T10:00:00'
            if isinstance(value, Decimal):
                return float(value)  # or str(value)
            return value

        result = {}
        mapper = inspect(self).mapper

        # Include column attributes
        for column in mapper.column_attrs:
            value = getattr(self, column.key)
            result[column.key] = serialize_value(value)

        if include_relationships:
            for rel in mapper.relationships:
                value = getattr(self, rel.key)
                if value is None:
                    result[rel.key] = None
                elif rel.uselist:  # one-to-many, many-to-many
                    result[rel.key] = [v.to_dict() for v in value]
                else:  # many-to-one, one-to-one
                    result[rel.key] = value.to_dict()

        return result

class Base(DeclarativeBase, ToDictMixin):
    pass