"""PostgreSQL schema introspection.

This module provides functionality to introspect PostgreSQL database schemas,
extracting comprehensive metadata about tables, columns, constraints, indexes,
and custom types.
"""


from asyncpg import Pool
from asyncpg.connection import Connection

from pg_mcp.models.schema import (
    ColumnInfo,
    DatabaseSchema,
    EnumTypeInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableInfo,
)


class SchemaIntrospector:
    """PostgreSQL schema introspection service.

    This class provides methods to extract complete schema metadata from
    a PostgreSQL database using system catalogs.

    Attributes:
        pool: Database connection pool.
        database_name: Name of the database being introspected.
    """

    def __init__(self, pool: Pool, database_name: str):
        """Initialize schema introspector.

        Args:
            pool: asyncpg connection pool.
            database_name: Name of the database to introspect.
        """
        self.pool = pool
        self.database_name = database_name

    async def introspect(self) -> DatabaseSchema:
        """Execute complete schema introspection.

        This method fetches all schema metadata including tables, views,
        columns, constraints, indexes, and custom types.

        Returns:
            DatabaseSchema: Complete database schema information.

        Example:
            >>> introspector = SchemaIntrospector(pool, "mydb")
            >>> schema = await introspector.introspect()
            >>> print(f"Found {len(schema.tables)} tables")
        """
        async with self.pool.acquire() as conn:
            # Get PostgreSQL version
            version_result = await conn.fetchval("SELECT version()")
            version = version_result.split(",")[0] if version_result else None

            # Fetch all schema components concurrently
            tables = await self._get_tables(conn)
            views = await self._get_views(conn)
            enum_types = await self._get_enum_types(conn)

            # Enrich tables with detailed information
            for table in tables + views:
                table.columns = await self._get_columns(conn, table.table_name, table.schema_name)
                primary_keys = await self._get_primary_keys(
                    conn, table.table_name, table.schema_name
                )

                # Mark primary key columns
                for col in table.columns:
                    if col.name in primary_keys:
                        col.is_primary_key = True

                table.foreign_keys = await self._get_foreign_keys(
                    conn, table.table_name, table.schema_name
                )
                table.indexes = await self._get_indexes(conn, table.table_name, table.schema_name)
                table.row_count_estimate = await self._get_row_count_estimate(
                    conn, table.table_name, table.schema_name
                )

            return DatabaseSchema(
                database_name=self.database_name,
                tables=tables + views,
                enum_types=enum_types,
                version=version,
            )

    async def _get_tables(self, conn: Connection) -> list[TableInfo]:
        """Get all user tables (excluding system tables).

        Args:
            conn: Database connection.

        Returns:
            list[TableInfo]: List of table information objects.
        """
        query = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                obj_description(c.oid, 'pg_class') AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'  -- regular tables only
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY n.nspname, c.relname
        """

        rows = await conn.fetch(query)

        return [
            TableInfo(
                schema_name=row["schema_name"],
                table_name=row["table_name"],
                comment=row["comment"],
                row_count_estimate=None,
            )
            for row in rows
        ]

    async def _get_columns(
        self, conn: Connection, table_name: str, schema_name: str
    ) -> list[ColumnInfo]:
        """Get column information for a specific table.

        Args:
            conn: Database connection.
            table_name: Name of the table.
            schema_name: Schema name.

        Returns:
            list[ColumnInfo]: List of column information objects.
        """
        query = """
            SELECT
                a.attname AS column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                NOT a.attnotnull AS is_nullable,
                pg_get_expr(ad.adbin, ad.adrelid) AS default_value,
                col_description(a.attrelid, a.attnum) AS comment
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            LEFT JOIN pg_attrdef ad ON a.attrelid = ad.adrelid AND a.attnum = ad.adnum
            WHERE c.relname = $1
              AND n.nspname = $2
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
        """

        rows = await conn.fetch(query, table_name, schema_name)

        columns = []
        for row in rows:
            # Check if column has unique constraint
            is_unique = await self._is_column_unique(
                conn, table_name, schema_name, row["column_name"]
            )

            columns.append(
                ColumnInfo(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    is_nullable=row["is_nullable"],
                    default_value=row["default_value"],
                    is_unique=is_unique,
                    comment=row["comment"],
                )
            )

        return columns

    async def _is_column_unique(
        self, conn: Connection, table_name: str, schema_name: str, column_name: str
    ) -> bool:
        """Check if a column has a unique constraint (excluding primary key).

        Args:
            conn: Database connection.
            table_name: Name of the table.
            schema_name: Schema name.
            column_name: Name of the column.

        Returns:
            bool: True if column has a unique constraint.
        """
        query = """
            SELECT EXISTS(
                SELECT 1
                FROM pg_constraint con
                JOIN pg_class c ON con.conrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(con.conkey)
                WHERE c.relname = $1
                  AND n.nspname = $2
                  AND a.attname = $3
                  AND con.contype = 'u'  -- unique constraint
            )
        """

        result = await conn.fetchval(query, table_name, schema_name, column_name)
        return bool(result) if result is not None else False

    async def _get_primary_keys(
        self, conn: Connection, table_name: str, schema_name: str
    ) -> list[str]:
        """Get primary key column names for a table.

        Args:
            conn: Database connection.
            table_name: Name of the table.
            schema_name: Schema name.

        Returns:
            list[str]: List of primary key column names.
        """
        query = """
            SELECT a.attname AS column_name
            FROM pg_index i
            JOIN pg_class c ON i.indrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
            WHERE c.relname = $1
              AND n.nspname = $2
              AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
        """

        rows = await conn.fetch(query, table_name, schema_name)
        return [row["column_name"] for row in rows]

    async def _get_foreign_keys(
        self, conn: Connection, table_name: str, schema_name: str
    ) -> list[ForeignKeyInfo]:
        """Get foreign key relationships for a table.

        Args:
            conn: Database connection.
            table_name: Name of the table.
            schema_name: Schema name.

        Returns:
            list[ForeignKeyInfo]: List of foreign key information objects.
        """
        query = """
            SELECT
                con.conname AS constraint_name,
                a.attname AS column_name,
                ref_c.relname AS referenced_table,
                ref_a.attname AS referenced_column
            FROM pg_constraint con
            JOIN pg_class c ON con.conrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            JOIN pg_attribute a
                ON a.attrelid = c.oid AND a.attnum = ANY(con.conkey)
            JOIN pg_class ref_c ON con.confrelid = ref_c.oid
            JOIN pg_attribute ref_a
                ON ref_a.attrelid = ref_c.oid
                AND ref_a.attnum = ANY(con.confkey)
            WHERE c.relname = $1
              AND n.nspname = $2
              AND con.contype = 'f'  -- foreign key
            ORDER BY con.conname
        """

        rows = await conn.fetch(query, table_name, schema_name)

        return [
            ForeignKeyInfo(
                constraint_name=row["constraint_name"],
                column_name=row["column_name"],
                referenced_table=row["referenced_table"],
                referenced_column=row["referenced_column"],
            )
            for row in rows
        ]

    async def _get_indexes(
        self, conn: Connection, table_name: str, schema_name: str
    ) -> list[IndexInfo]:
        """Get index information for a table.

        Args:
            conn: Database connection.
            table_name: Name of the table.
            schema_name: Schema name.

        Returns:
            list[IndexInfo]: List of index information objects.
        """
        query = """
            SELECT
                i.relname AS index_name,
                idx.indisunique AS is_unique,
                am.amname AS index_type,
                ARRAY(
                    SELECT a.attname
                    FROM pg_attribute a
                    WHERE a.attrelid = idx.indrelid
                      AND a.attnum = ANY(idx.indkey)
                    ORDER BY array_position(idx.indkey, a.attnum)
                ) AS columns
            FROM pg_index idx
            JOIN pg_class i ON i.oid = idx.indexrelid
            JOIN pg_class c ON c.oid = idx.indrelid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            JOIN pg_am am ON i.relam = am.oid
            WHERE c.relname = $1
              AND n.nspname = $2
              AND NOT idx.indisprimary  -- exclude primary key indexes
            ORDER BY i.relname
        """

        rows = await conn.fetch(query, table_name, schema_name)

        return [
            IndexInfo(
                name=row["index_name"],
                columns=list(row["columns"]),
                is_unique=row["is_unique"],
                index_type=row["index_type"],
            )
            for row in rows
        ]

    async def _get_views(self, conn: Connection) -> list[TableInfo]:
        """Get all user views.

        Args:
            conn: Database connection.

        Returns:
            list[TableInfo]: List of view information objects.
        """
        query = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                obj_description(c.oid, 'pg_class') AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'v'  -- views only
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, c.relname
        """

        rows = await conn.fetch(query)

        return [
            TableInfo(
                schema_name=row["schema_name"],
                table_name=row["table_name"],
                comment=row["comment"],
                row_count_estimate=None,
            )
            for row in rows
        ]

    async def _get_enum_types(self, conn: Connection) -> list[EnumTypeInfo]:
        """Get custom ENUM type definitions.

        Args:
            conn: Database connection.

        Returns:
            list[EnumTypeInfo]: List of enum type information objects.
        """
        query = """
            SELECT
                n.nspname AS schema_name,
                t.typname AS type_name,
                ARRAY(
                    SELECT e.enumlabel
                    FROM pg_enum e
                    WHERE e.enumtypid = t.oid
                    ORDER BY e.enumsortorder
                ) AS values
            FROM pg_type t
            JOIN pg_namespace n ON t.typnamespace = n.oid
            WHERE t.typtype = 'e'  -- enum types only
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, t.typname
        """

        rows = await conn.fetch(query)

        return [
            EnumTypeInfo(
                schema_name=row["schema_name"],
                type_name=row["type_name"],
                values=list(row["values"]),
            )
            for row in rows
        ]

    async def _get_row_count_estimate(
        self, conn: Connection, table_name: str, schema_name: str
    ) -> int:
        """Get estimated row count for a table.

        This uses PostgreSQL's statistics rather than COUNT(*) for better
        performance on large tables.

        Args:
            conn: Database connection.
            table_name: Name of the table.
            schema_name: Schema name.

        Returns:
            int: Estimated number of rows.
        """
        query = """
            SELECT reltuples::bigint AS estimate
            FROM pg_class c
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = $1
              AND n.nspname = $2
        """

        result = await conn.fetchval(query, table_name, schema_name)
        return int(result) if result is not None else 0
