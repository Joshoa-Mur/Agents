from typing import Optional
from pydantic import BaseModel, Field
import duckdb

class FindOrderArgs(BaseModel):
    """
    Аргументы для поиска заказа в базе данных Olist.
    Используется агентом поддержки, когда клиенту нужно найти информацию 
    по его заказу с помощью email или уникального идентификатора заказа.
    """
    customer_email: Optional[str] = Field(
        default=None, 
        description="Email клиента, по которому нужно найти его заказы в базе."
    )
    order_id: Optional[str] = Field(
        default=None,
        description="Уникальный идентификатор заказа (order_id), если он известен."
    )

class CheckOrderStatus(BaseModel):
    """
    Аргументы для поиска информации о заказах в базе данных Olist.
    Используется агентом поддержки, когда клиенту нужно узнать статус заказа, 
    проверить детали или найти недавние покупки.
    """
    customer_email: Optional[str] = Field(
        default=None, 
        description="Email клиента, по которому нужно найти все его заказы в базе."
    )
    order_id: Optional[str] = Field(
        default=None,
        description="Уникальный идентификатор конкретного заказа (order_id), если клиент его назвал."
    )
    order_status: Optional[str] = Field(
        default=None,
        description="Статус заказа для фильтрации (например: shipped, delivered, processing, canceled)."
    )



def find_order(args: FindOrderArgs) -> str:
    """Выполняет поиск заказа в DuckDB по переданным аргументам"""
    con = duckdb.connect("olist.db")

    try:
        if args.order_id:
            query = """
                SELECT 
                    o.order_id,
                    o.order_status,
                    o.order_purchase_timestamp,
                    c.customer_city
                    с.customer_email
                FROM olist_orders o 
                JOIN olist_customers c ON o.customer_id = c.customer_id
                WHERE o.order_id = ?
            """
            
            result = con.execute(query, [args.order_id]).fetchall()
            
        elif args.customer_email:
            if args.order_id:
                query = """
                    SELECT 
                        o.order_id,
                        o.order_status,
                        o.order_purchase_timestamp,
                        c.customer_city
                        с.customer_email
                    FROM olist_orders o 
                    JOIN olist_customers c ON o.customer_id = c.customer_id
                    WHERE c.customer_email= ?
                """
                        
                result = con.execute(query, [args.customer_email]).fetchall()
            
            
        else:
            return "Уточните order_id или email для поиска заказа."

        
        if not result:
            return "Заказ не найден в базе данных."

        return str(result)
        
    finally:
        con.close()