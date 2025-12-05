"""
Подключение к БД service_center и простые методы работы с заявками.

Для работы нужен локальный MySQL / MariaDB сервер.
Перед использованием укажите корректные параметры соединения в DB_CONFIG.
"""

import mysql.connector
from mysql.connector import MySQLConnection
from typing import Any, Dict, List, Optional, Tuple


DB_CONFIG: Dict[str, Any] = {
    "host": "localhost",
    "user": "root",        # замените на своего пользователя
    "password": "0210",        # укажите пароль
    "database": "service_center",
    "auth_plugin": "mysql_native_password",
}


def get_connection() -> MySQLConnection:
    """Создаёт и возвращает подключение к БД."""
    return mysql.connector.connect(**DB_CONFIG)


def init_db_from_sql(sql_file: str = "service_center.sql") -> None:
    """
    Одноразовая инициализация БД из SQL-скрипта.
    Запускается вручную при первом развёртывании.
    """
    with open(sql_file, "r", encoding="utf-8") as f:
        sql = f.read()

    # В MySQL удобно выполнять скрипт по частям, разделённым ;
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    conn = mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        auth_plugin=DB_CONFIG.get("auth_plugin", "mysql_native_password"),
    )
    cur = conn.cursor()
    for stmt in statements:
        cur.execute(stmt)
    conn.commit()
    cur.close()
    conn.close()


def fetch_client_requests(phone: str) -> List[Dict[str, Any]]:
    """
    Получить список заявок по номеру телефона клиента.
    Возвращает словари с основной информацией.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT r.request_id,
               r.start_date,
               et.type_name    AS equipment_type,
               e.model         AS model,
               r.problem_description,
               rs.status_name  AS status,
               r.completion_date,
               r.report,
               r.notify_client,
               r.client_id,
               u.lastname,
               u.firstname,
               u.surname
        FROM requests r
        JOIN users u             ON r.client_id = u.user_id
        JOIN equipment e         ON r.equipment_id = e.equipment_id
        JOIN equipment_types et  ON e.type_id = et.type_id
        JOIN request_statuses rs ON r.status_id = rs.status_id
        WHERE u.phone = %s
        ORDER BY r.start_date DESC, r.request_id DESC;
    """
    cur.execute(query, (phone,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_request_comments(request_id: int) -> List[Dict[str, Any]]:
    """Получить историю комментариев по заявке."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    query = """
        SELECT c.comment_id,
               c.message,
               c.created_at,
               u.firstname,
               u.lastname,
               r.role_name
        FROM comments c
        JOIN users u ON c.user_id = u.user_id
        JOIN roles r ON u.role_id = r.role_id
        WHERE c.request_id = %s
        ORDER BY c.created_at ASC, c.comment_id ASC;
    """
    cur.execute(query, (request_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def add_comment(request_id: int, user_id: int, message: str) -> None:
    """Добавить комментарий к заявке."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO comments (message, user_id, request_id) VALUES (%s, %s, %s)",
        (message, user_id, request_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def add_attachment(request_id: int, user_id: Optional[int], file_path: str, description: str = "") -> None:
    """Добавить вложение к заявке."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO attachments (request_id, user_id, file_path, description)
        VALUES (%s, %s, %s, %s)
        """,
        (request_id, user_id, file_path, description),
    )
    conn.commit()
    cur.close()
    conn.close()


def fetch_attachments(request_id: int) -> List[Dict[str, Any]]:
    """Получить список вложений по заявке."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT a.attachment_id,
               a.file_path,
               a.description,
               a.uploaded_at,
               u.firstname,
               u.lastname
        FROM attachments a
        LEFT JOIN users u ON a.user_id = u.user_id
        WHERE a.request_id = %s
        ORDER BY a.uploaded_at ASC, a.attachment_id ASC
        """,
        (request_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def update_request_status_and_report(
    request_id: int,
    status_id: int,
    report: Optional[str] = None,
    notify_client: bool = False,
) -> None:
    """Обновить статус заявки, отчёт и флаг оповещения клиента."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE requests
        SET status_id = %s,
            report = COALESCE(%s, report),
            notify_client = %s
        WHERE request_id = %s
        """,
        (status_id, report, int(bool(notify_client)), request_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def set_request_requires_parts(request_id: int, requires_parts: bool = True) -> None:
    """Отметить, что по заявке требуется заказ запчастей."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE requests SET requires_parts = %s WHERE request_id = %s",
        (int(bool(requires_parts)), request_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def _split_full_name(full_name: str) -> Tuple[str, str, str]:
    """
    Вспомогательная функция: разбиение ФИО на фамилию, имя и отчество.
    При неполном вводе заполняет недостающие части дефисами.
    """
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "-", "-", "-"
    if len(parts) == 1:
        return parts[0], "-", "-"
    if len(parts) == 2:
        return parts[0], parts[1], "-"
    return parts[0], parts[1], " ".join(parts[2:])


def get_or_create_client(full_name: str, phone: str) -> int:
    """
    Найти клиента по телефону с ролью 'Заказчик' или создать нового.
    Возвращает user_id.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Найти роль "Заказчик"
    cur.execute("SELECT role_id FROM roles WHERE role_name = %s", ("Заказчик",))
    row = cur.fetchone()
    if not row:
        # Создадим роль при необходимости
        cur.execute("INSERT INTO roles (role_name) VALUES (%s)", ("Заказчик",))
        role_id = cur.lastrowid
    else:
        role_id = row[0]

    # Попробовать найти существующего пользователя
    cur.execute(
        "SELECT user_id FROM users WHERE phone = %s AND role_id = %s",
        (phone, role_id),
    )
    row = cur.fetchone()
    if row:
        user_id = row[0]
        cur.close()
        conn.close()
        return user_id

    # Создать нового заказчика
    lastname, firstname, surname = _split_full_name(full_name)
    login = f"client_{phone}"
    password = "client"  # учебный проект, без хеширования
    cur.execute(
        """
        INSERT INTO users (lastname, firstname, surname, phone, login, password, role_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (lastname, firstname, surname, phone, login, password, role_id),
    )
    user_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return user_id


def get_or_create_equipment(type_name: str, model: str) -> int:
    """Найти или создать запись об оборудовании по типу и модели. Возвращает equipment_id."""
    conn = get_connection()
    cur = conn.cursor()

    # Тип оборудования
    cur.execute(
        "SELECT type_id FROM equipment_types WHERE type_name = %s",
        (type_name,),
    )
    row = cur.fetchone()
    if row:
        type_id = row[0]
    else:
        cur.execute(
            "INSERT INTO equipment_types (type_name) VALUES (%s)",
            (type_name,),
        )
        type_id = cur.lastrowid

    # Конкретное устройство (тип + модель)
    cur.execute(
        "SELECT equipment_id FROM equipment WHERE type_id = %s AND model = %s",
        (type_id, model),
    )
    row = cur.fetchone()
    if row:
        equipment_id = row[0]
    else:
        cur.execute(
            "INSERT INTO equipment (type_id, model) VALUES (%s, %s)",
            (type_id, model),
        )
        equipment_id = cur.lastrowid

    conn.commit()
    cur.close()
    conn.close()
    return equipment_id


def _get_status_id(status_name: str) -> int:
    """Вспомогательная функция: получить ID статуса по имени (создаёт при необходимости)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT status_id FROM request_statuses WHERE status_name = %s",
        (status_name,),
    )
    row = cur.fetchone()
    if row:
        status_id = row[0]
    else:
        cur.execute(
            "INSERT INTO request_statuses (status_name) VALUES (%s)",
            (status_name,),
        )
        status_id = cur.lastrowid
        conn.commit()
    cur.close()
    conn.close()
    return status_id


def get_status_id(status_name: str) -> int:
    """
    Публичная обёртка для получения ID статуса по имени.
    Удобна для GUI-кода.
    """
    return _get_status_id(status_name)


def create_request(client_id: int, equipment_id: int, problem_description: str) -> int:
    """
    Создать новую заявку от клиента:
    - статус по умолчанию: 'Новая заявка'
    - дата начала: текущая дата БД
    Возвращает request_id.
    """
    status_id = _get_status_id("Новая заявка")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO requests (start_date, equipment_id, problem_description, status_id, client_id)
        VALUES (CURRENT_DATE, %s, %s, %s, %s)
        """,
        (equipment_id, problem_description, status_id, client_id),
    )
    request_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return request_id


def update_request_client_side(
    request_id: int,
    new_problem_description: Optional[str] = None,
    new_model: Optional[str] = None,
) -> None:
    """
    Обновить описание проблемы и/или модель устройства по заявке со стороны клиента.
    Внимание: изменение модели изменяет запись в таблице equipment для данной заявки.
    """
    conn = get_connection()
    cur = conn.cursor()

    if new_problem_description:
        cur.execute(
            "UPDATE requests SET problem_description = %s WHERE request_id = %s",
            (new_problem_description, request_id),
        )

    if new_model:
        # Найти оборудование, связанное с заявкой, и обновить модель
        cur.execute(
            "SELECT equipment_id FROM requests WHERE request_id = %s",
            (request_id,),
        )
        row = cur.fetchone()
        if row:
            equipment_id = row[0]
            cur.execute(
                "UPDATE equipment SET model = %s WHERE equipment_id = %s",
                (new_model, equipment_id),
            )

    conn.commit()
    cur.close()
    conn.close()


def fetch_all_requests() -> List[Dict[str, Any]]:
    """
    Получить список всех заявок с основной информацией для оператора:
    клиент, телефон, устройство, статус, приоритет, назначенный мастер.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    query = """
        SELECT
          r.request_id,
          r.start_date,
          r.problem_description,
          rs.status_name      AS status,
          r.priority,
          r.ticket_type,
          r.operator_group,
          r.responsible_operator,
          r.observers_text,
          r.notify_client,
          r.requires_parts,
          r.report,
          c.user_id           AS client_id,
          c.lastname          AS client_lastname,
          c.firstname         AS client_firstname,
          c.surname           AS client_surname,
          c.phone             AS client_phone,
          e.equipment_id,
          et.type_name        AS equipment_type,
          e.model             AS equipment_model,
          m.user_id           AS master_id,
          m.lastname          AS master_lastname,
          m.firstname         AS master_firstname
        FROM requests r
        JOIN users c              ON r.client_id = c.user_id
        JOIN equipment e          ON r.equipment_id = e.equipment_id
        JOIN equipment_types et   ON e.type_id = et.type_id
        JOIN request_statuses rs  ON r.status_id = rs.status_id
        LEFT JOIN users m         ON r.master_id = m.user_id
        ORDER BY r.start_date DESC, r.request_id DESC
    """
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def search_requests(text: str) -> List[Dict[str, Any]]:
    """
    Поиск заявок по различным полям для электронного архива оператора.
    Ищем по: ID, ФИО/телефону клиента, типу/модели устройства, описанию, статусу, приоритету, типу заявки.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    pattern = f"%{text.lower()}%"
    query = """
        SELECT
          r.request_id,
          r.start_date,
          r.problem_description,
          rs.status_name      AS status,
          r.priority,
          r.ticket_type,
          r.operator_group,
          r.responsible_operator,
          r.observers_text,
          r.notify_client,
          r.requires_parts,
          r.report,
          c.user_id           AS client_id,
          c.lastname          AS client_lastname,
          c.firstname         AS client_firstname,
          c.surname           AS client_surname,
          c.phone             AS client_phone,
          e.equipment_id,
          et.type_name        AS equipment_type,
          e.model             AS equipment_model,
          m.user_id           AS master_id,
          m.lastname          AS master_lastname,
          m.firstname         AS master_firstname
        FROM requests r
        JOIN users c              ON r.client_id = c.user_id
        JOIN equipment e          ON r.equipment_id = e.equipment_id
        JOIN equipment_types et   ON e.type_id = et.type_id
        JOIN request_statuses rs  ON r.status_id = rs.status_id
        LEFT JOIN users m         ON r.master_id = m.user_id
        WHERE
          CAST(r.request_id AS CHAR) LIKE %s OR
          LOWER(CONCAT(c.lastname, ' ', c.firstname, ' ', c.surname)) LIKE %s OR
          LOWER(c.phone)           LIKE %s OR
          LOWER(et.type_name)      LIKE %s OR
          LOWER(e.model)           LIKE %s OR
          LOWER(r.problem_description) LIKE %s OR
          LOWER(rs.status_name)    LIKE %s OR
          LOWER(r.priority)        LIKE %s OR
          LOWER(r.ticket_type)     LIKE %s
        ORDER BY r.start_date DESC, r.request_id DESC
    """
    params = (pattern,) * 9
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def _get_user_id_by_master_name(name: str) -> Optional[int]:
    """
    Найти мастера по ФИО (по фамилии или логину).
    Используется при назначении мастера оператором.
    """
    name = name.strip()
    if not name:
        return None
    conn = get_connection()
    cur = conn.cursor()
    # Попробуем найти по фамилии, затем по логину
    cur.execute(
        """
        SELECT user_id
        FROM users
        WHERE lastname = %s OR login = %s
        LIMIT 1
        """,
        (name, name),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0]
    return None


def get_user_id_by_name_or_login(name: str) -> Optional[int]:
    """
    Публичная функция для поиска пользователя по фамилии или логину.
    Используется во вкладке мастера для получения user_id.
    """
    return _get_user_id_by_master_name(name)


def update_request_operator_side(
    request_id: int,
    operator_group: Optional[str],
    responsible_operator: Optional[str],
    observers_text: Optional[str],
    status_name: Optional[str],
    priority: Optional[str],
    ticket_type: Optional[str],
    master_name: Optional[str],
) -> None:
    """
    Обновление полей заявки со стороны оператора:
    группа операторов, ответственный, наблюдатели, статус, приоритет, тип, мастер.
    """
    conn = get_connection()
    cur = conn.cursor()

    status_id: Optional[int] = None
    if status_name:
        status_id = _get_status_id(status_name)

    master_id: Optional[int] = None
    if master_name:
        master_id = _get_user_id_by_master_name(master_name)

    # Сформируем запрос динамически, обновляя только переданные поля
    fields = []
    params: List[Any] = []
    if operator_group is not None:
        fields.append("operator_group = %s")
        params.append(operator_group)
    if responsible_operator is not None:
        fields.append("responsible_operator = %s")
        params.append(responsible_operator)
    if observers_text is not None:
        fields.append("observers_text = %s")
        params.append(observers_text)
    if status_id is not None:
        fields.append("status_id = %s")
        params.append(status_id)
    if priority is not None:
        fields.append("priority = %s")
        params.append(priority)
    if ticket_type is not None:
        fields.append("ticket_type = %s")
        params.append(ticket_type)
    if master_name is not None:
        fields.append("master_id = %s")
        params.append(master_id)

    if fields:
        sql = f"UPDATE requests SET {', '.join(fields)} WHERE request_id = %s"
        params.append(request_id)
        cur.execute(sql, tuple(params))

    conn.commit()
    cur.close()
    conn.close()


def delete_request(request_id: int) -> None:
    """Удалить заявку (каскадно удалятся комментарии, вложения и запчасти по внешним ключам)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM requests WHERE request_id = %s", (request_id,))
    conn.commit()
    cur.close()
    conn.close()


def fetch_requests_for_master(master_id: int) -> List[Dict[str, Any]]:
    """
    Получить список заявок, назначенных конкретному мастеру.
    Используется во вкладке мастера, сортировка по приоритету.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    query = """
        SELECT
          r.request_id,
          r.start_date,
          r.problem_description,
          rs.status_name      AS status,
          r.priority,
          r.ticket_type,
          r.operator_group,
          r.responsible_operator,
          r.observers_text,
          r.notify_client,
          r.requires_parts,
          r.report,
          c.user_id           AS client_id,
          c.lastname          AS client_lastname,
          c.firstname         AS client_firstname,
          c.surname           AS client_surname,
          c.phone             AS client_phone,
          e.equipment_id,
          et.type_name        AS equipment_type,
          e.model             AS equipment_model
        FROM requests r
        JOIN users c              ON r.client_id = c.user_id
        JOIN equipment e          ON r.equipment_id = e.equipment_id
        JOIN equipment_types et   ON e.type_id = et.type_id
        JOIN request_statuses rs  ON r.status_id = rs.status_id
        WHERE r.master_id = %s
        ORDER BY
          CASE r.priority
            WHEN 'Высокий' THEN 1
            WHEN 'Средний' THEN 2
            WHEN 'Низкий'  THEN 3
            ELSE 4
          END,
          r.start_date,
          r.request_id
    """
    cur.execute(query, (master_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows




