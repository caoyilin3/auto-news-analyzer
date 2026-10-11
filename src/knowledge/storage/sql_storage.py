"""
SQL数据库存储实现
支持多种SQL数据库：SQLite、PostgreSQL、MySQL
"""

import sqlite3
import threading
import json
import pickle
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import warnings

try:
    import psycopg2
    from psycopg2 import pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    warnings.warn("psycopg2 not installed, PostgreSQL support disabled")

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    warnings.warn("mysql-connector-python not installed, MySQL support disabled")

from .base_storage import (
    BaseStorage, StorageConfig, StorageRecord, StorageQuery,
    StorageResult, StorageOperation, StorageError
)

class DatabaseType(Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"

@dataclass
class SQLStorageConfig(StorageConfig):
    """SQL存储配置"""
    db_type: DatabaseType = DatabaseType.SQLITE
    db_name: str = "knowledge.db"
    table_name: str = "storage_records"
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    pool_size: int = 5  # 连接池大小
    timeout_seconds: int = 30
    isolation_level: str = "READ COMMITTED"
    
    # 表结构配置
    id_field: str = "id"
    data_field: str = "data"
    metadata_field: str = "metadata"
    version_field: str = "version"
    created_at_field: str = "created_at"
    updated_at_field: str = "updated_at"
    partition_field: str = "partition_key"

class SQLStorage(BaseStorage):
    """SQL数据库存储实现"""
    
    def __init__(self, config: SQLStorageConfig):
        super().__init__(config)
        self.config = config
        self.db_type = config.db_type
        
        # 数据库连接
        self._connection_pool = None
        self._local_connection = threading.local()
        
        # SQL方言
        self._dialect = self._get_dialect()
        
        # 表名和字段名
        self._table_name = self._sanitize_identifier(config.table_name)
        self._id_field = self._sanitize_identifier(config.id_field)
        self._data_field = self._sanitize_identifier(config.data_field)
        self._metadata_field = self._sanitize_identifier(config.metadata_field)
        self._version_field = self._sanitize_identifier(config.version_field)
        self._created_at_field = self._sanitize_identifier(config.created_at_field)
        self._updated_at_field = self._sanitize_identifier(config.updated_at_field)
        self._partition_field = self._sanitize_identifier(config.partition_field)
    
    def _get_dialect(self) -> Dict[str, str]:
        """获取SQL方言"""
        if self.db_type == DatabaseType.SQLITE:
            return {
                "auto_increment": "AUTOINCREMENT",
                "datetime_now": "CURRENT_TIMESTAMP",
                "ilike": "LIKE",
                "concat": "||",
                "limit_offset": "LIMIT ? OFFSET ?"
            }
        elif self.db_type == DatabaseType.POSTGRESQL:
            return {
                "auto_increment": "SERIAL",
                "datetime_now": "NOW()",
                "ilike": "ILIKE",
                "concat": "||",
                "limit_offset": "LIMIT ? OFFSET ?"
            }
        elif self.db_type == DatabaseType.MYSQL:
            return {
                "auto_increment": "AUTO_INCREMENT",
                "datetime_now": "NOW()",
                "ilike": "LIKE",
                "concat": "CONCAT",
                "limit_offset": "LIMIT ? OFFSET ?"
            }
        else:
            return {}
    
    def _sanitize_identifier(self, identifier: str) -> str:
        """清理标识符"""
        # 移除危险字符，只保留字母数字和下划线
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
        if not sanitized:
            sanitized = "default"
        return sanitized
    
    def initialize(self) -> bool:
        """初始化SQL存储"""
        try:
            # 创建连接池
            self._create_connection_pool()
            
            # 创建表
            self._create_tables()
            
            # 创建索引
            if self.config.auto_index:
                self._create_indexes()
            
            self.initialized = True
            return True
            
        except Exception as e:
            raise StorageError(
                f"Failed to initialize SQL storage: {e}",
                StorageOperation.CREATE,
                "INIT_ERROR"
            )
    
    def _create_connection_pool(self):
        """创建连接池"""
        if self.db_type == DatabaseType.SQLITE:
            # SQLite使用简单的连接管理
            self._connection_pool = None
        elif self.db_type == DatabaseType.POSTGRESQL:
            if not PSYCOPG2_AVAILABLE:
                raise ImportError("psycopg2 is required for PostgreSQL support")
            
            conn_str = self.config.connection_string or \
                f"dbname={self.config.db_name} " \
                f"host={self.config.host} " \
                f"port={self.config.port} " \
                f"user={self.config.username} " \
                f"password={self.config.password}"
            
            self._connection_pool = pool.SimpleConnectionPool(
                1, self.config.pool_size, conn_str
            )
        elif self.db_type == DatabaseType.MYSQL:
            if not MYSQL_AVAILABLE:
                raise ImportError("mysql-connector-python is required for MySQL support")
            
            # MySQL连接池
            self._connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="mysql_pool",
                pool_size=self.config.pool_size,
                host=self.config.host,
                port=self.config.port,
                user=self.config.username,
                password=self.config.password,
                database=self.config.db_name
            )
    
    def _get_connection(self):
        """获取数据库连接"""
        if hasattr(self._local_connection, 'conn'):
            return self._local_connection.conn
        
        if self.db_type == DatabaseType.SQLITE:
            conn = sqlite3.connect(
                self.config.connection_string or self.config.db_name,
                timeout=self.config.timeout_seconds
            )
            conn.row_factory = sqlite3.Row
            
        elif self.db_type == DatabaseType.POSTGRESQL:
            if self._connection_pool:
                conn = self._connection_pool.getconn()
            else:
                raise StorageError(
                    "PostgreSQL connection pool not initialized",
                    StorageOperation.CREATE,
                    "CONNECTION_ERROR"
                )
        
        elif self.db_type == DatabaseType.MYSQL:
            if self._connection_pool:
                conn = self._connection_pool.get_connection()
            else:
                raise StorageError(
                    "MySQL connection pool not initialized",
                    StorageOperation.CREATE,
                    "CONNECTION_ERROR"
                )
        
        else:
            raise StorageError(
                f"Unsupported database type: {self.db_type}",
                StorageOperation.CREATE,
                "UNSUPPORTED_DB"
            )
        
        self._local_connection.conn = conn
        return conn
    
    def _release_connection(self, conn):
        """释放数据库连接"""
        if self.db_type == DatabaseType.POSTGRESQL and self._connection_pool:
            self._connection_pool.putconn(conn)
        elif self.db_type == DatabaseType.MYSQL and self._connection_pool:
            conn.close()
        
        if hasattr(self._local_connection, 'conn'):
            del self._local_connection.conn
    
    def _create_tables(self):
        """创建表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 创建主表
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                {self._id_field} VARCHAR(255) PRIMARY KEY,
                {self._data_field} TEXT NOT NULL,
                {self._metadata_field} TEXT,
                {self._version_field} INTEGER DEFAULT 1,
                {self._created_at_field} TIMESTAMP DEFAULT {self._dialect['datetime_now']},
                {self._updated_at_field} TIMESTAMP DEFAULT {self._dialect['datetime_now']},
                {self._partition_field} VARCHAR(255)
            )
            """
            
            cursor.execute(create_table_sql)
            
            # 创建历史表（用于版本控制）
            create_history_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self._table_name}_history (
                id VARCHAR(255),
                version INTEGER,
                {self._data_field} TEXT NOT NULL,
                {self._metadata_field} TEXT,
                changed_at TIMESTAMP DEFAULT {self._dialect['datetime_now']},
                changed_by VARCHAR(255),
                PRIMARY KEY (id, version)
            )
            """
            
            cursor.execute(create_history_table_sql)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            self._release_connection(conn)
    
    def _create_indexes(self):
        """创建索引"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 创建常用索引
            indexes = [
                f"CREATE INDEX IF NOT EXISTS idx_{self._table_name}_created_at "
                f"ON {self._table_name} ({self._created_at_field})",
                
                f"CREATE INDEX IF NOT EXISTS idx_{self._table_name}_updated_at "
                f"ON {self._table_name} ({self._updated_at_field})",
                
                f"CREATE INDEX IF NOT EXISTS idx_{self._table_name}_partition "
                f"ON {self._table_name} ({self._partition_field})",
                
                f"CREATE INDEX IF NOT EXISTS idx_{self._table_name}_version "
                f"ON {self._table_name} ({self._version_field})"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            self._release_connection(conn)
    
    def create(self, record: StorageRecord) -> StorageResult:
        """创建记录"""
        import time
        start_time = time.time()
        
        try:
            # 验证记录
            is_valid, error_msg = self._validate_record(record)
            if not is_valid:
                raise StorageError(error_msg, StorageOperation.CREATE)
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 检查记录是否存在
                check_sql = f"SELECT COUNT(*) FROM {self._table_name} WHERE {self._id_field} = ?"
                cursor.execute(check_sql, (record.id,))
                count = cursor.fetchone()[0]
                
                if count > 0:
                    raise StorageError(
                        f"Record {record.id} already exists",
                        StorageOperation.CREATE,
                        "DUPLICATE_RECORD"
                    )
                
                # 插入记录
                insert_sql = f"""
                INSERT INTO {self._table_name} (
                    {self._id_field}, {self._data_field}, {self._metadata_field},
                    {self._version_field}, {self._partition_field}
                ) VALUES (?, ?, ?, ?, ?)
                """
                
                data_json = json.dumps(record.data, default=str)
                metadata_json = json.dumps(record.metadata, default=str)
                
                cursor.execute(insert_sql, (
                    record.id,
                    data_json,
                    metadata_json,
                    record.version,
                    record.partition_key
                ))
                
                # 插入历史记录
                history_sql = f"""
                INSERT INTO {self._table_name}_history (
                    {self._id_field}, {self._version_field}, {self._data_field},
                    {self._metadata_field}, changed_by
                ) VALUES (?, ?, ?, ?, ?)
                """
                
                cursor.execute(history_sql, (
                    record.id,
                    record.version,
                    data_json,
                    metadata_json,
                    "system"
                ))
                
                conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.CREATE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.CREATE,
                    data=record,
                    metadata={
                        "record_id": record.id,
                        "version": record.version,
                        "execution_time_ms": execution_time
                    }
                )
                
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except StorageError as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise e
        except Exception as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise StorageError(
                f"Failed to create record: {e}",
                StorageOperation.CREATE,
                "CREATE_ERROR"
            )
    
    def read(self, record_id: str) -> StorageResult:
        """读取记录"""
        import time
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 查询记录
                select_sql = f"""
                SELECT * FROM {self._table_name} 
                WHERE {self._id_field} = ?
                """
                
                cursor.execute(select_sql, (record_id,))
                row = cursor.fetchone()
                
                if not row:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.READ,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 转换为StorageRecord
                record = self._row_to_record(row)
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.READ, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.READ,
                    data=record,
                    metadata={
                        "record_id": record_id,
                        "execution_time_ms": execution_time
                    }
                )
                
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except Exception as e:
            self._record_operation(StorageOperation.READ, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def update(self, record_id: str, data: Dict[str, Any], 
              metadata: Optional[Dict[str, Any]] = None) -> StorageResult:
        """更新记录"""
        import time
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 获取原记录
                select_sql = f"""
                SELECT * FROM {self._table_name} 
                WHERE {self._id_field} = ?
                """
                
                cursor.execute(select_sql, (record_id,))
                row = cursor.fetchone()
                
                if not row:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.UPDATE,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                old_record = self._row_to_record(row)
                
                # 合并元数据
                new_metadata = old_record.metadata.copy()
                if metadata:
                    new_metadata.update(metadata)
                
                # 创建新记录
                new_record = StorageRecord(
                    id=record_id,
                    data=data,
                    metadata=new_metadata,
                    version=old_record.version + 1,
                    created_at=old_record.created_at,
                    updated_at=datetime.now(),
                    partition_key=old_record.partition_key
                )
                
                # 验证新记录
                is_valid, error_msg = self._validate_record(new_record)
                if not is_valid:
                    raise StorageError(error_msg, StorageOperation.UPDATE)
                
                # 更新记录
                update_sql = f"""
                UPDATE {self._table_name} 
                SET {self._data_field} = ?, 
                    {self._metadata_field} = ?,
                    {self._version_field} = ?,
                    {self._updated_at_field} = ?
                WHERE {self._id_field} = ?
                """
                
                data_json = json.dumps(data, default=str)
                metadata_json = json.dumps(new_metadata, default=str)
                
                cursor.execute(update_sql, (
                    data_json,
                    metadata_json,
                    new_record.version,
                    new_record.updated_at,
                    record_id
                ))
                
                # 插入历史记录
                history_sql = f"""
                INSERT INTO {self._table_name}_history (
                    {self._id_field}, {self._version_field}, {self._data_field},
                    {self._metadata_field}, changed_by
                ) VALUES (?, ?, ?, ?, ?)
                """
                
                cursor.execute(history_sql, (
                    record_id,
                    new_record.version,
                    data_json,
                    metadata_json,
                    "system"
                ))
                
                conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.UPDATE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.UPDATE,
                    data=new_record,
                    metadata={
                        "record_id": record_id,
                        "old_version": old_record.version,
                        "new_version": new_record.version,
                        "execution_time_ms": execution_time
                    }
                )
                
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except StorageError as e:
            self._record_operation(StorageOperation.UPDATE, False)
            raise e
        except Exception as e:
            self._record_operation(StorageOperation.UPDATE, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def delete(self, record_id: str) -> StorageResult:
        """删除记录"""
        import time
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 检查记录是否存在
                check_sql = f"SELECT COUNT(*) FROM {self._table_name} WHERE {self._id_field} = ?"
                cursor.execute(check_sql, (record_id,))
                count = cursor.fetchone()[0]
                
                if count == 0:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.DELETE,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 删除记录
                delete_sql = f"DELETE FROM {self._table_name} WHERE {self._id_field} = ?"
                cursor.execute(delete_sql, (record_id,))
                
                conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.DELETE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.DELETE,
                    data={"record_id": record_id},
                    metadata={
                        "record_id": record_id,
                        "execution_time_ms": execution_time
                    }
                )
                
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except Exception as e:
            self._record_operation(StorageOperation.DELETE, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def search(self, query: StorageQuery) -> StorageResult:
        """搜索记录"""
        import time
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 构建SQL查询
                sql_parts = []
                params = []
                
                # SELECT子句
                select_fields = "*"
                if query.projections:
                    select_fields = ", ".join(query.projections)
                
                sql_parts.append(f"SELECT {select_fields} FROM {self._table_name}")
                
                # WHERE子句
                where_conditions = []
                for field_name, filter_value in query.filters.items():
                    if isinstance(filter_value, dict):
                        # 复杂查询操作符
                        for op, op_value in filter_value.items():
                            condition, condition_params = self._build_condition(
                                field_name, op, op_value
                            )
                            where_conditions.append(condition)
                            params.extend(condition_params)
                    else:
                        # 简单等于
                        where_conditions.append(f"{field_name} = ?")
                        params.append(filter_value)
                
                if where_conditions:
                    sql_parts.append(f"WHERE {' AND '.join(where_conditions)}")
                
                # ORDER BY子句
                if query.sort_by:
                    order_parts = []
                    for field_name, direction in query.sort_by:
                        order_parts.append(f"{field_name} {direction}")
                    sql_parts.append(f"ORDER BY {', '.join(order_parts)}")
                
                # LIMIT和OFFSET子句
                if query.limit or query.offset:
                    sql_parts.append("LIMIT ? OFFSET ?")
                    params.append(query.limit or 999999)
                    params.append(query.offset)
                
                # 执行查询
                sql = " ".join(sql_parts)
                cursor.execute(sql, params)
                
                # 获取结果
                rows = cursor.fetchall()
                records = [self._row_to_record(row) for row in rows]
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.SEARCH, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.SEARCH,
                    data=records,
                    metadata={
                        "total_returned": len(records),
                        "execution_time_ms": execution_time
                    }
                )
                
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except Exception as e:
            self._record_operation(StorageOperation.SEARCH, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _build_condition(self, field_name: str, operator: str, value: Any) -> Tuple[str, List[Any]]:
        """构建查询条件"""
        if operator == "$eq":
            return f"{field_name} = ?", [value]
        elif operator == "$ne":
            return f"{field_name} != ?", [value]
        elif operator == "$gt":
            return f"{field_name} > ?", [value]
        elif operator == "$gte":
            return f"{field_name} >= ?", [value]
        elif operator == "$lt":
            return f"{field_name} < ?", [value]
        elif operator == "$lte":
            return f"{field_name} <= ?", [value]
        elif operator == "$in":
            if isinstance(value, list):
                placeholders = ", ".join(["?"] * len(value))
                return f"{field_name} IN ({placeholders})", value
            else:
                return f"{field_name} = ?", [value]
        elif operator == "$nin":
            if isinstance(value, list):
                placeholders = ", ".join(["?"] * len(value))
                return f"{field_name} NOT IN ({placeholders})", value
            else:
                return f"{field_name} != ?", [value]
        elif operator == "$like":
            return f"{field_name} LIKE ?", [f"%{value}%"]
        elif operator == "$ilike":
            return f"{field_name} {self._dialect['ilike']} ?", [f"%{value}%"]
        else:
            raise ValueError(f"Unsupported operator: {operator}")
    
    def _row_to_record(self, row) -> StorageRecord:
        """将数据库行转换为StorageRecord"""
        # 获取字段值
        id_value = row[self.config.id_field] if isinstance(row, dict) else row[0]
        
        # 解析JSON字段
        try:
            data_value = json.loads(row[self.config.data_field]) if isinstance(row, dict) else json.loads(row[1])
        except:
            data_value = {}
        
        try:
            metadata_value = json.loads(row[self.config.metadata_field]) if isinstance(row, dict) else json.loads(row[2])
        except:
            metadata_value = {}
        
        # 获取其他字段
        version_value = row[self.config.version_field] if isinstance(row, dict) else row[3]
        created_at_value = row[self.config.created_at_field] if isinstance(row, dict) else row[4]
        updated_at_value = row[self.config.updated_at_field] if isinstance(row, dict) else row[5]
        partition_value = row[self.config.partition_field] if isinstance(row, dict) else row[6] if len(row) > 6 else None
        
        # 转换时间字段
        if isinstance(created_at_value, str):
            try:
                created_at_value = datetime.fromisoformat(created_at_value.replace('Z', '+00:00'))
            except:
                created_at_value = datetime.now()
        
        if isinstance(updated_at_value, str):
            try:
                updated_at_value = datetime.fromisoformat(updated_at_value.replace('Z', '+00:00'))
            except:
                updated_at_value = datetime.now()
        
        return StorageRecord(
            id=id_value,
            data=data_value,
            metadata=metadata_value,
            version=version_value,
            created_at=created_at_value,
            updated_at=updated_at_value,
            partition_key=partition_value
        )
    
    def get_history(self, record_id: str) -> StorageResult:
        """获取记录历史"""
        import time
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 查询历史记录
                select_sql = f"""
                SELECT * FROM {self._table_name}_history 
                WHERE {self._id_field} = ? 
                ORDER BY {self._version_field} DESC
                """
                
                cursor.execute(select_sql, (record_id,))
                rows = cursor.fetchall()
                
                history = []
                for row in rows:
                    history.append({
                        "version": row[1],
                        "data": json.loads(row[2]) if isinstance(row[2], str) else row[2],
                        "metadata": json.loads(row[3]) if isinstance(row[3], str) else row[3],
                        "changed_at": row[4],
                        "changed_by": row[5]
                    })
                
                execution_time = (time.time() - start_time) * 1000
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.READ,
                    data=history,
                    metadata={
                        "record_id": record_id,
                        "history_count": len(history),
                        "execution_time_ms": execution_time
                    }
                )
                
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def get_version(self, record_id: str, version: int) -> StorageResult:
        """获取特定版本记录"""
        import time
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 查询历史版本
                select_sql = f"""
                SELECT * FROM {self._table_name}_history 
                WHERE {self._id_field} = ? AND {self._version_field} = ?
                """
                
                cursor.execute(select_sql, (record_id, version))
                row = cursor.fetchone()
                
                if not row:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.READ,
                        error=f"Version {version} of record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 创建记录
                record_data = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                record_metadata = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                
                record = StorageRecord(
                    id=record_id,
                    data=record_data,
                    metadata=record_metadata,
                    version=version
                )
                
                execution_time = (time.time() - start_time) * 1000
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.READ,
                    data=record,
                    metadata={
                        "record_id": record_id,
                        "version": version,
                        "execution_time_ms": execution_time
                    }
                )
                
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def backup(self, backup_path: str) -> StorageResult:
        """备份数据库"""
        import time
        start_time = time.time()
        
        try:
            if self.db_type == DatabaseType.SQLITE:
                import shutil
                shutil.copy2(self.config.db_name, backup_path)
            else:
                # 对于其他数据库，导出为SQL
                conn = self._get_connection()
                cursor = conn.cursor()
                
                try:
                    # 获取所有记录
                    select_sql = f"SELECT * FROM {self._table_name}"
                    cursor.execute(select_sql)
                    rows = cursor.fetchall()
                    
                    # 导出到JSON
                    records = [self._row_to_record(row) for row in rows]
                    backup_data = {
                        "database": self.db_type.value,
                        "table": self._table_name,
                        "backup_time": datetime.now().isoformat(),
                        "record_count": len(records),
                        "records": [record.to_dict() for record in records]
                    }
                    
                    import json
                    with open(backup_path, 'w') as f:
                        json.dump(backup_data, f, indent=2, default=str)
                        
                finally:
                    cursor.close()
                    self._release_connection(conn)
            
            execution_time = (time.time() - start_time) * 1000
            
            return StorageResult(
                success=True,
                operation=StorageOperation.CREATE,
                data={"backup_path": backup_path},
                metadata={
                    "execution_time_ms": execution_time,
                    "backup_size": self._get_file_size(backup_path)
                }
            )
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.CREATE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _get_file_size(self, filepath: str) -> int:
        """获取文件大小"""
        import os
        try:
            return os.path.getsize(filepath)
        except:
            return 0
    
    def restore(self, backup_path: str) -> StorageResult:
        """恢复数据库"""
        import time
        start_time = time.time()
        
        try:
            import json
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            # 清空现有数据
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 删除现有数据
                delete_sql = f"DELETE FROM {self._table_name}"
                cursor.execute(delete_sql)
                
                # 恢复记录
                records_data = backup_data.get("records", [])
                for record_data in records_data:
                    record = StorageRecord.from_dict(record_data)
                    
                    insert_sql = f"""
                    INSERT INTO {self._table_name} (
                        {self._id_field}, {self._data_field}, {self._metadata_field},
                        {self._version_field}, {self._partition_field}
                    ) VALUES (?, ?, ?, ?, ?)
                    """
                    
                    data_json = json.dumps(record.data, default=str)
                    metadata_json = json.dumps(record.metadata, default=str)
                    
                    cursor.execute(insert_sql, (
                        record.id,
                        data_json,
                        metadata_json,
                        record.version,
                        record.partition_key
                    ))
                
                conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.UPDATE,
                    data={"restored_records": len(records_data)},
                    metadata={
                        "execution_time_ms": execution_time,
                        "record_count": len(records_data)
                    }
                )
                
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def get_table_stats(self) -> StorageResult:
        """获取表统计信息"""
        import time
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # 获取记录总数
                count_sql = f"SELECT COUNT(*) FROM {self._table_name}"
                cursor.execute(count_sql)
                total_records = cursor.fetchone()[0]
                
                # 获取版本总数
                version_sql = f"SELECT COUNT(*) FROM {self._table_name}_history"
                cursor.execute(version_sql)
                total_versions = cursor.fetchone()[0]
                
                # 获取分区统计
                partition_sql = f"""
                SELECT {self._partition_field}, COUNT(*) 
                FROM {self._table_name} 
                WHERE {self._partition_field} IS NOT NULL 
                GROUP BY {self._partition_field}
                """
                cursor.execute(partition_sql)
                partition_stats = {row[0]: row[1] for row in cursor.fetchall()}
                
                execution_time = (time.time() - start_time) * 1000
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.READ,
                    data={
                        "total_records": total_records,
                        "total_versions": total_versions,
                        "partition_stats": partition_stats
                    },
                    metadata={
                        "execution_time_ms": execution_time
                    }
                )
                
            finally:
                cursor.close()
                self._release_connection(conn)
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def close(self):
        """关闭存储"""
        if hasattr(self._local_connection, 'conn'):
            try:
                self._local_connection.conn.close()
            except:
                pass
        
        if self._connection_pool:
            if self.db_type == DatabaseType.POSTGRESQL:
                self._connection_pool.closeall()
            elif self.db_type == DatabaseType.MYSQL:
                self._connection_pool._remove_connections()
        
        self.initialized = False