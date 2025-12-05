"""
Модели данных и файловое хранилище (JSON) для системы учёта заявок на ремонт оргтехники.

Используется как внутренний модуль логики (в том числе в ticket_gui.py).
Консольное меню и запуск из командной строки удалены: проект ориентирован на GUI и/или БД.

Хранение: JSON-файл tickets_data.json.
Для реляционной БД см. файлы service_center.sql и db_connection.py.
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any


DATA_FILE = "tickets_data.json"


def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {"tickets": [], "next_id": 1}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Message:
    def __init__(self, author_role: str, author_name: str, text: str, created_at: Optional[str] = None):
        self.author_role = author_role
        self.author_name = author_name
        self.text = text
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "author_role": self.author_role,
            "author_name": self.author_name,
            "text": self.text,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Message":
        return Message(
            author_role=data["author_role"],
            author_name=data["author_name"],
            text=data["text"],
            created_at=data["created_at"],
        )


class Attachment:
    def __init__(self, filename: str, description: str = ""):
        self.filename = filename
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "description": self.description,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Attachment":
        return Attachment(
            filename=data["filename"],
            description=data.get("description", ""),
        )


class Ticket:
    def __init__(
        self,
        ticket_id: int,
        device_type: str,
        device_model: str,
        problem_description: str,
        client_name: str,
        client_phone: str,
        status: str = "Новая",
        priority: str = "Средний",
        ticket_type: str = "Стандартная",
        operator_group: str = "",
        responsible_operator: str = "",
        observers: Optional[List[str]] = None,
        assigned_master: str = "",
        history: Optional[List[Message]] = None,
        attachments: Optional[List[Attachment]] = None,
        requires_parts: bool = False,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        report: str = "",
        notify_client: bool = False,
    ):
        self.ticket_id = ticket_id
        self.device_type = device_type
        self.device_model = device_model
        self.problem_description = problem_description
        self.client_name = client_name
        self.client_phone = client_phone
        self.status = status
        self.priority = priority
        self.ticket_type = ticket_type
        self.operator_group = operator_group
        self.responsible_operator = responsible_operator
        self.observers = observers or []
        self.assigned_master = assigned_master
        self.history = history or []
        self.attachments = attachments or []
        self.requires_parts = requires_parts
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M")
        self.updated_at = updated_at or self.created_at
        self.report = report
        self.notify_client = notify_client

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "device_type": self.device_type,
            "device_model": self.device_model,
            "problem_description": self.problem_description,
            "client_name": self.client_name,
            "client_phone": self.client_phone,
            "status": self.status,
            "priority": self.priority,
            "ticket_type": self.ticket_type,
            "operator_group": self.operator_group,
            "responsible_operator": self.responsible_operator,
            "observers": self.observers,
            "assigned_master": self.assigned_master,
            "history": [m.to_dict() for m in self.history],
            "attachments": [a.to_dict() for a in self.attachments],
            "requires_parts": self.requires_parts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "report": self.report,
            "notify_client": self.notify_client,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Ticket":
        return Ticket(
            ticket_id=data["ticket_id"],
            device_type=data["device_type"],
            device_model=data["device_model"],
            problem_description=data["problem_description"],
            client_name=data["client_name"],
            client_phone=data["client_phone"],
            status=data.get("status", "Новая"),
            priority=data.get("priority", "Средний"),
            ticket_type=data.get("ticket_type", "Стандартная"),
            operator_group=data.get("operator_group", ""),
            responsible_operator=data.get("responsible_operator", ""),
            observers=data.get("observers", []),
            assigned_master=data.get("assigned_master", ""),
            history=[Message.from_dict(m) for m in data.get("history", [])],
            attachments=[Attachment.from_dict(a) for a in data.get("attachments", [])],
            requires_parts=data.get("requires_parts", False),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            report=data.get("report", ""),
            notify_client=data.get("notify_client", False),
        )

    def add_message(self, message: Message) -> None:
        self.history.append(message)
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    def add_attachment(self, attachment: Attachment) -> None:
        self.attachments.append(attachment)
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")


class TicketSystem:
    def __init__(self):
        self.data = load_data()
        self.tickets: List[Ticket] = [Ticket.from_dict(t) for t in self.data.get("tickets", [])]
        self.next_id: int = self.data.get("next_id", 1)

    def _save(self) -> None:
        self.data["tickets"] = [t.to_dict() for t in self.tickets]
        self.data["next_id"] = self.next_id
        save_data(self.data)
