"""Database schema models for PostgreSQL introspection.

This module defines data models representing PostgreSQL database schema
including tables, columns, foreign keys, indexes, and enum types.
"""

from typing import Any

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """Information about a database column."""

    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="PostgreSQL data type")
    is_nullable: bool = Field(..., description="Whether column allows NULL values")
    default_value: str | None = Field(None, description="Default value expression")
    is_primary_key: bool = Field(default=False, description="Whether column is primary key")
    is_unique: bool = Field(default=False, description="Whether column has unique constraint")
    comment: str | None = Field(None, description="Column comment/description")

    def to_prompt_line(self) -> str:
        """Format column info for LLM prompt.

        Returns:
            str: Formatted column description.
        """
        parts = [f"  - {self.name}: {self.data_type}"]

        flags = []
        if self.is_primary_key:
            flags.append("PRIMARY KEY")
        if self.is_unique and not self.is_primary_key:
            flags.append("UNIQUE")
        if not self.is_nullable:
            flags.append("NOT NULL")
        if self.default_value:
            flags.append(f"DEFAULT {self.default_value}")

        if flags:
            parts.append(f" ({', '.join(flags)})")

        if self.comment:
            parts.append(f" -- {self.comment}")

        return "".join(parts)


class ForeignKeyInfo(BaseModel):
    """Information about a foreign key relationship."""

    constraint_name: str = Field(..., description="Foreign key constraint name")
    column_name: str = Field(..., description="Column name in source table")
    referenced_table: str = Field(..., description="Referenced table name")
    referenced_column: str = Field(..., description="Referenced column name")

    def to_prompt_line(self) -> str:
        """Format foreign key info for LLM prompt.

        Returns:
            str: Formatted foreign key description.
        """
        return f"  - {self.column_name} -> {self.referenced_table}.{self.referenced_column}"


class IndexInfo(BaseModel):
    """Information about a database index."""

    name: str = Field(..., description="Index name")
    columns: list[str] = Field(..., description="Indexed column names")
    is_unique: bool = Field(default=False, description="Whether index is unique")
    index_type: str = Field(default="btree", description="Index type (btree, hash, gin, etc.)")

    def to_prompt_line(self) -> str:
        """Format index info for LLM prompt.

        Returns:
            str: Formatted index description.
        """
        idx_type = "UNIQUE " if self.is_unique else ""
        cols = ", ".join(self.columns)
        return f"  - {idx_type}{self.index_type.upper()} INDEX on ({cols})"


class TableInfo(BaseModel):
    """Complete information about a database table."""

    schema_name: str = Field(default="public", description="Schema name")
    table_name: str = Field(..., description="Table name")
    columns: list[ColumnInfo] = Field(default_factory=list, description="Table columns")
    foreign_keys: list[ForeignKeyInfo] = Field(
        default_factory=list, description="Foreign key relationships"
    )
    indexes: list[IndexInfo] = Field(default_factory=list, description="Table indexes")
    comment: str | None = Field(None, description="Table comment/description")
    row_count_estimate: int | None = Field(None, description="Estimated row count")

    @property
    def full_name(self) -> str:
        """Get fully qualified table name.

        Returns:
            str: Schema-qualified table name.
        """
        return f"{self.schema_name}.{self.table_name}"

    def to_prompt_section(self) -> str:
        """Format table info for LLM prompt.

        Returns:
            str: Formatted table description for inclusion in schema context.
        """
        lines = [f"\nTable: {self.full_name}"]

        if self.comment:
            lines.append(f"Description: {self.comment}")

        if self.row_count_estimate is not None:
            lines.append(f"Approximate rows: {self.row_count_estimate:,}")

        lines.append("\nColumns:")
        for col in self.columns:
            lines.append(col.to_prompt_line())

        if self.foreign_keys:
            lines.append("\nForeign Keys:")
            for fk in self.foreign_keys:
                lines.append(fk.to_prompt_line())

        if self.indexes:
            lines.append("\nIndexes:")
            for idx in self.indexes:
                lines.append(idx.to_prompt_line())

        return "\n".join(lines)


class EnumTypeInfo(BaseModel):
    """Information about a PostgreSQL ENUM type."""

    schema_name: str = Field(default="public", description="Schema name")
    type_name: str = Field(..., description="Enum type name")
    values: list[str] = Field(..., description="Allowed enum values")

    @property
    def full_name(self) -> str:
        """Get fully qualified enum type name.

        Returns:
            str: Schema-qualified type name.
        """
        return f"{self.schema_name}.{self.type_name}"

    def to_prompt_line(self) -> str:
        """Format enum info for LLM prompt.

        Returns:
            str: Formatted enum description.
        """
        values = ", ".join(f"'{v}'" for v in self.values)
        return f"  - {self.type_name}: {values}"


class DatabaseSchema(BaseModel):
    """Complete database schema information."""

    database_name: str = Field(..., description="Database name")
    tables: list[TableInfo] = Field(default_factory=list, description="Database tables")
    enum_types: list[EnumTypeInfo] = Field(default_factory=list, description="Custom enum types")
    version: str | None = Field(None, description="PostgreSQL version")

    def get_table(self, table_name: str, schema_name: str = "public") -> TableInfo | None:
        """Find table by name.

        Args:
            table_name: Name of the table to find.
            schema_name: Schema name (defaults to 'public').

        Returns:
            TableInfo if found, None otherwise.
        """
        for table in self.tables:
            if table.table_name == table_name and table.schema_name == schema_name:
                return table
        return None

    def to_prompt_context(self) -> str:
        """Generate complete schema context for LLM prompt.

        This method creates a comprehensive yet concise representation of the
        database schema suitable for inclusion in LLM prompts for SQL generation.

        Returns:
            str: Formatted schema context string.
        """
        lines = [f"Database: {self.database_name}"]

        if self.version:
            lines.append(f"PostgreSQL Version: {self.version}")

        if self.enum_types:
            lines.append("\n=== Custom Types ===")
            for enum in self.enum_types:
                lines.append(enum.to_prompt_line())

        if self.tables:
            lines.append("\n=== Tables ===")
            for table in self.tables:
                lines.append(table.to_prompt_section())

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert schema to dictionary representation.

        Returns:
            dict: Dictionary representation of the schema.
        """
        return self.model_dump()
