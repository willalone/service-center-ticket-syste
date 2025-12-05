"""
Графический интерфейс (PyQt5) для системы учёта заявок на ремонт оргтехники.

Вкладки:
- «Клиент»   — создание/редактирование заявок, просмотр, история, вложения, оповещение о выполнении.
- «Оператор» — список заявок, распределение по операторам и наблюдателям, статусы/приоритеты/типы, поиск и дубликаты.
- «Мастер»   — список назначенных заявок по приоритету, заказ запчастей, изменение статуса, отчёт, вложения.

Все данные и операции выполняются напрямую в БД MySQL/MariaDB (см. service_center.sql и db_connection.py).
"""

import sys
from typing import Optional, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QInputDialog,
)

from db_connection import (
    get_or_create_client,
    get_or_create_equipment,
    create_request,
    fetch_client_requests,
    fetch_request_comments,
    add_attachment as db_add_attachment,
    add_comment,
    update_request_client_side,
    fetch_all_requests,
    search_requests,
    update_request_operator_side,
    delete_request,
    fetch_requests_for_master,
    set_request_requires_parts,
    update_request_status_and_report,
    get_user_id_by_name_or_login,
    get_status_id,
)


class ClientTab(QWidget):
    def __init__(self, system: Optional[object] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # system сохраняется только для совместимости сигнатуры,
        # но клиентская вкладка работает напрямую с БД через db_connection.
        self.system = system
        self.current_request: Optional[dict] = None
        self.requests: List[dict] = []

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Блок "Новая заявка" ---
        new_group = QGroupBox("Новая заявка")
        new_layout = QFormLayout()
        new_layout.setLabelAlignment(Qt.AlignRight)
        new_layout.setHorizontalSpacing(15)
        new_layout.setVerticalSpacing(8)

        self.client_name_edit = QLineEdit()
        self.client_phone_edit = QLineEdit()
        self.device_type_edit = QLineEdit()
        self.device_model_edit = QLineEdit()
        self.problem_edit = QTextEdit()

        new_layout.addRow("ФИО клиента:", self.client_name_edit)
        new_layout.addRow("Телефон:", self.client_phone_edit)
        new_layout.addRow("Вид оргтехники:", self.device_type_edit)
        new_layout.addRow("Модель:", self.device_model_edit)
        new_layout.addRow("Описание проблемы:", self.problem_edit)

        self.create_btn = QPushButton("Создать заявку")
        self.create_btn.clicked.connect(self.create_ticket)
        new_layout.addRow(self.create_btn)

        new_group.setLayout(new_layout)
        main_layout.addWidget(new_group)

        # --- Блок "Поиск и список заявок клиента" ---
        search_group = QGroupBox("Мои заявки")
        search_layout = QVBoxLayout()

        search_form = QHBoxLayout()
        self.search_name_edit = QLineEdit()
        self.search_phone_edit = QLineEdit()
        search_btn = QPushButton("Найти")
        search_btn.clicked.connect(self.search_tickets)
        search_form.addWidget(QLabel("ФИО:"))
        search_form.addWidget(self.search_name_edit)
        search_form.addWidget(QLabel("Телефон:"))
        search_form.addWidget(self.search_phone_edit)
        search_form.addWidget(search_btn)

        self.client_table = QTableWidget(0, 5)
        self.client_table.setHorizontalHeaderLabels(
            ["ID", "Устройство", "Модель", "Статус", "Приоритет"]
        )
        self.client_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.client_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.client_table.horizontalHeader().setStretchLastSection(True)
        self.client_table.verticalHeader().setVisible(False)
        self.client_table.cellClicked.connect(self.on_ticket_selected)

        search_layout.addLayout(search_form)
        search_layout.addWidget(self.client_table)

        search_group.setLayout(search_layout)
        main_layout.addWidget(search_group)

        # --- Блок "Детали заявки" ---
        detail_group = QGroupBox("Детали заявки")
        detail_layout = QVBoxLayout()

        self.ticket_info_label = QLabel("Заявка не выбрана.")
        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)

        edit_form = QFormLayout()
        edit_form.setLabelAlignment(Qt.AlignRight)
        edit_form.setHorizontalSpacing(15)
        edit_form.setVerticalSpacing(8)
        self.edit_model = QLineEdit()
        self.edit_problem = QTextEdit()
        edit_form.addRow("Модель:", self.edit_model)
        edit_form.addRow("Описание проблемы:", self.edit_problem)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.save_edit_btn = QPushButton("Сохранить изменения")
        self.save_edit_btn.clicked.connect(self.save_client_changes)
        attach_btn = QPushButton("Прикрепить файл")
        attach_btn.clicked.connect(self.attach_file)
        notify_btn = QPushButton("Проверить оповещения")
        notify_btn.clicked.connect(self.check_notifications)
        btn_row.addWidget(self.save_edit_btn)
        btn_row.addWidget(attach_btn)
        btn_row.addWidget(notify_btn)

        detail_layout.addWidget(self.ticket_info_label)
        detail_layout.addLayout(edit_form)
        detail_layout.addLayout(btn_row)
        detail_layout.addWidget(QLabel("История переписки:"))
        detail_layout.addWidget(self.history_view)

        detail_group.setLayout(detail_layout)
        main_layout.addWidget(detail_group)

        self.setLayout(main_layout)

    def create_ticket(self) -> None:
        name = self.client_name_edit.text().strip()
        phone = self.client_phone_edit.text().strip()
        dtype = self.device_type_edit.text().strip()
        dmodel = self.device_model_edit.text().strip()
        problem = self.problem_edit.toPlainText().strip()

        if not (name and phone and dtype and problem):
            QMessageBox.warning(self, "Ошибка", "Заполните обязательные поля (ФИО, телефон, вид, проблема).")
            return

        # создаём (или находим) клиента и оборудование в БД и регистрируем заявку
        client_id = get_or_create_client(name, phone)
        equipment_id = get_or_create_equipment(dtype, dmodel or "Модель не указана")
        request_id = create_request(client_id, equipment_id, problem)

        QMessageBox.information(
            self,
            "Успех",
            f"Заявка создана. Номер заявки: {request_id}",
        )
        self.problem_edit.clear()

    def search_tickets(self) -> None:
        phone = self.search_phone_edit.text().strip()
        if not phone:
            QMessageBox.warning(self, "Ошибка", "Укажите телефон для поиска.")
            return
        # загрузка заявок клиента из БД
        tickets = fetch_client_requests(phone)
        self.requests = tickets
        self.client_table.setRowCount(0)
        for t in tickets:
            row = self.client_table.rowCount()
            self.client_table.insertRow(row)
            self.client_table.setItem(row, 0, QTableWidgetItem(str(t["request_id"])))
            self.client_table.setItem(row, 1, QTableWidgetItem(t["equipment_type"]))
            self.client_table.setItem(row, 2, QTableWidgetItem(t["model"]))
            self.client_table.setItem(row, 3, QTableWidgetItem(t["status"]))
            self.client_table.setItem(row, 4, QTableWidgetItem("-"))
        if not tickets:
            QMessageBox.information(self, "Результат", "Заявки не найдены.")
        self.current_request = None
        self.update_details()

    def _get_selected_request(self) -> Optional[dict]:
        row = self.client_table.currentRow()
        if row < 0:
            return None
        if row >= len(self.requests):
            return None
        return self.requests[row]

    def on_ticket_selected(self, row: int, column: int) -> None:
        _ = column  # unused
        self.current_request = self._get_selected_request()
        self.update_details()

    def update_details(self) -> None:
        r = self.current_request
        if not r:
            self.ticket_info_label.setText("Заявка не выбрана.")
            self.edit_model.clear()
            self.edit_problem.clear()
            self.history_view.clear()
            return
        self.ticket_info_label.setText(
            f"Заявка ID {r['request_id']}: {r['equipment_type']} {r['model']}, статус {r['status']}"
        )
        self.edit_model.setText(r["model"])
        self.edit_problem.setPlainText(r["problem_description"])

        # история комментариев из БД
        comments = fetch_request_comments(r["request_id"])
        history_lines: List[str] = []
        for c in comments:
            author = f"{c['lastname']} {c['firstname']}".strip()
            history_lines.append(f"[{c['created_at']}] {c['role_name']} {author}: {c['message']}")
        self.history_view.setPlainText("\n".join(history_lines))

    def save_client_changes(self) -> None:
        r = self.current_request
        if not r:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку.")
            return
        if r["status"] == "Готова к выдаче":
            QMessageBox.information(self, "Информация", "Завершённую заявку редактировать нельзя.")
            return
        new_model = self.edit_model.text().strip()
        new_problem = self.edit_problem.toPlainText().strip()
        update_request_client_side(
            request_id=r["request_id"],
            new_problem_description=new_problem or None,
            new_model=new_model or None,
        )
        QMessageBox.information(self, "Успех", "Изменения сохранены.")
        # перечитать заявки клиента
        self.search_tickets()

    def attach_file(self) -> None:
        r = self.current_request
        if not r:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл")
        if not path:
            return
        desc, ok = QInputDialog.getText(self, "Описание файла", "Краткое описание:")
        if not ok or not desc.strip():
            desc = "Файл клиента"
        # user_id клиента есть в текущей записи (client_id)
        client_id = r["client_id"]
        db_add_attachment(r["request_id"], client_id, path, desc)
        add_comment(r["request_id"], client_id, f"К заявке прикреплён файл: {path}")
        QMessageBox.information(self, "Успех", "Файл прикреплён.")
        self.update_details()

    def check_notifications(self) -> None:
        phone = self.search_phone_edit.text().strip()
        if not phone:
            QMessageBox.warning(self, "Ошибка", "Сначала укажите телефон и выполните поиск.")
            return
        # показываем завершённые заявки текущего клиента по данным из БД
        requests = fetch_client_requests(phone)
        completed = [r for r in requests if r["notify_client"]]
        if not completed:
            QMessageBox.information(self, "Оповещения", "Нет завершённых заявок, требующих оповещения.")
            return
        msg_lines = []
        for r in completed:
            msg_lines.append(
                f"Заявка ID {r['request_id']} по устройству {r['equipment_type']} {r['model']} выполнена. "
                f"Статус: {r['status']}. Отчёт: {r['report'] or 'нет отчёта'}"
            )
        QMessageBox.information(self, "Оповещения о выполнении", "\n\n".join(msg_lines))


class OperatorTab(QWidget):
    def __init__(self, system: Optional[object] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # system сохраняется только для совместимости, но в операторской вкладке
        # вся работа идёт напрямую с БД.
        self.system = system
        self.current_request: Optional[dict] = None
        self.requests: List[dict] = []

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Список заявок ---
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Клиент",
                "Телефон",
                "Устройство",
                "Статус",
                "Приоритет",
                "Мастер",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self.on_ticket_selected)

        main_layout.addWidget(QLabel("Список заявок:"))
        main_layout.addWidget(self.table)

        # --- Детали и управление ---
        detail_group = QGroupBox("Детали и распределение")
        detail_layout = QFormLayout()
        detail_layout.setLabelAlignment(Qt.AlignRight)
        detail_layout.setHorizontalSpacing(15)
        detail_layout.setVerticalSpacing(8)

        self.op_info_label = QLabel("Заявка не выбрана.")
        detail_layout.addRow(self.op_info_label)

        self.group_edit = QLineEdit()
        self.operator_edit = QLineEdit()
        self.observers_edit = QLineEdit()
        self.status_edit = QComboBox()
        self.status_edit.addItems(["Новая", "В работе", "Ожидает запчастей", "Завершена"])
        self.priority_edit = QComboBox()
        self.priority_edit.addItems(["Низкий", "Средний", "Высокий"])
        self.type_edit = QLineEdit()
        self.master_edit = QLineEdit()

        detail_layout.addRow("Группа операторов:", self.group_edit)
        detail_layout.addRow("Ответственный оператор:", self.operator_edit)
        detail_layout.addRow("Наблюдатели (через запятую):", self.observers_edit)
        detail_layout.addRow("Статус:", self.status_edit)
        detail_layout.addRow("Приоритет:", self.priority_edit)
        detail_layout.addRow("Тип заявки:", self.type_edit)
        detail_layout.addRow("Назначенный мастер:", self.master_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        save_btn = QPushButton("Сохранить изменения")
        save_btn.clicked.connect(self.save_operator_changes)
        dup_btn = QPushButton("Найти и удалить дубликаты")
        dup_btn.clicked.connect(self.delete_duplicates)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(dup_btn)

        detail_layout.addRow(btn_row)

        # Поиск по архиву
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        self.archive_search_edit = QLineEdit()
        archive_btn = QPushButton("Поиск в архиве")
        archive_btn.clicked.connect(self.search_archive)
        search_layout.addWidget(QLabel("Поиск в архиве:"))
        search_layout.addWidget(self.archive_search_edit)
        search_layout.addWidget(archive_btn)
        detail_layout.addRow(search_layout)

        detail_group.setLayout(detail_layout)
        main_layout.addWidget(detail_group)

        self.setLayout(main_layout)
        self.reload_table()

    def reload_table(self, requests: Optional[List[dict]] = None) -> None:
        """Перечитать и отобразить список заявок из БД."""
        if requests is None:
            requests = fetch_all_requests()
        self.requests = requests
        self.table.setRowCount(0)
        for r in requests:
            row = self.table.rowCount()
            self.table.insertRow(row)
            client_fio = f"{r['client_lastname']} {r['client_firstname']} {r['client_surname']}".strip()
            equipment = f"{r['equipment_type']} {r['equipment_model']}"
            master_name = "-"
            if r.get("master_lastname"):
                master_name = f"{r['master_lastname']} {r.get('master_firstname', '')}".strip()

            self.table.setItem(row, 0, QTableWidgetItem(str(r["request_id"])))
            self.table.setItem(row, 1, QTableWidgetItem(client_fio))
            self.table.setItem(row, 2, QTableWidgetItem(r["client_phone"]))
            self.table.setItem(row, 3, QTableWidgetItem(equipment))
            self.table.setItem(row, 4, QTableWidgetItem(r["status"]))
            self.table.setItem(row, 5, QTableWidgetItem(r["priority"]))
            self.table.setItem(row, 6, QTableWidgetItem(master_name))

    def _get_selected_request(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        if row >= len(self.requests):
            return None
        return self.requests[row]

    def on_ticket_selected(self, row: int, column: int) -> None:
        _ = row, column
        self.current_request = self._get_selected_request()
        self.update_details()

    def update_details(self) -> None:
        r = self.current_request
        if not r:
            self.op_info_label.setText("Заявка не выбрана.")
            self.group_edit.clear()
            self.operator_edit.clear()
            self.observers_edit.clear()
            self.type_edit.clear()
            self.master_edit.clear()
            return
        self.op_info_label.setText(
            f"Заявка ID {r['request_id']}, клиент {r['client_lastname']} {r['client_firstname']}, "
            f"устройство {r['equipment_type']} {r['equipment_model']}"
        )
        self.group_edit.setText(r.get("operator_group") or "")
        self.operator_edit.setText(r.get("responsible_operator") or "")
        self.observers_edit.setText(r.get("observers_text") or "")
        # установить статус и приоритет в комбобоксы
        idx = self.status_edit.findText(r["status"])
        if idx >= 0:
            self.status_edit.setCurrentIndex(idx)
        idx = self.priority_edit.findText(r.get("priority", "Средний"))
        if idx >= 0:
            self.priority_edit.setCurrentIndex(idx)
        self.type_edit.setText(r.get("ticket_type") or "Стандартная")
        # мастер может быть не назначен
        if r.get("master_lastname"):
            self.master_edit.setText(r["master_lastname"])
        else:
            self.master_edit.clear()

    def save_operator_changes(self) -> None:
        r = self.current_request
        if not r:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку.")
            return
        operator_group = self.group_edit.text().strip()
        responsible_operator = self.operator_edit.text().strip()
        observers_text = self.observers_edit.text().strip()
        status_name = self.status_edit.currentText()
        priority = self.priority_edit.currentText()
        ticket_type = self.type_edit.text().strip() or "Стандартная"
        master_name = self.master_edit.text().strip() or None

        update_request_operator_side(
            request_id=r["request_id"],
            operator_group=operator_group or None,
            responsible_operator=responsible_operator or None,
            observers_text=observers_text or None,
            status_name=status_name,
            priority=priority,
            ticket_type=ticket_type,
            master_name=master_name,
        )
        self.reload_table()
        QMessageBox.information(self, "Успех", "Изменения по заявке сохранены.")

    def delete_duplicates(self) -> None:
        # Поиск и удаление дубликатов по клиенту (телефон) и описанию проблемы
        requests = fetch_all_requests()
        seen = {}
        for r in requests:
            key = (
                r["client_phone"],
                (r["problem_description"] or "").strip().lower(),
            )
            if key in seen:
                orig_id = seen[key]
                reply = QMessageBox.question(
                    self,
                    "Дубликат заявки",
                    f"Найден дубликат заявки ID {r['request_id']} (оригинал ID {orig_id}). Удалить?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    delete_request(r["request_id"])
            else:
                seen[key] = r["request_id"]

        self.reload_table()
        QMessageBox.information(self, "Результат", "Поиск дубликатов завершён.")

    def search_archive(self) -> None:
        text = self.archive_search_edit.text().strip().lower()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Введите текст для поиска.")
            return
        found = search_requests(text)
        if not found:
            QMessageBox.information(self, "Поиск", "Ничего не найдено.")
            return
        self.reload_table(found)


class MasterTab(QWidget):
    def __init__(self, system: Optional[object] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # system сохраняется только для совместимости, но вкладка мастера
        # использует только БД.
        self.system = system
        self.current_request: Optional[dict] = None
        self.master_name: str = ""
        self.master_id: Optional[int] = None
        self.requests: List[dict] = []

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Выбор мастера ---
        master_layout = QHBoxLayout()
        master_layout.setSpacing(10)
        self.master_edit = QLineEdit()
        set_master_btn = QPushButton("Установить имя мастера")
        set_master_btn.clicked.connect(self.set_master)
        master_layout.addWidget(QLabel("Имя мастера:"))
        master_layout.addWidget(self.master_edit)
        master_layout.addWidget(set_master_btn)
        main_layout.addLayout(master_layout)

        # --- Список назначенных заявок ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Устройство", "Модель", "Статус", "Приоритет"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self.on_ticket_selected)

        main_layout.addWidget(QLabel("Назначенные заявки:"))
        main_layout.addWidget(self.table)

        # --- Детали заявки ---
        detail_group = QGroupBox("Работа по заявке")
        detail_layout = QFormLayout()
        detail_layout.setLabelAlignment(Qt.AlignRight)
        detail_layout.setHorizontalSpacing(15)
        detail_layout.setVerticalSpacing(8)

        self.master_info_label = QLabel("Заявка не выбрана.")
        detail_layout.addRow(self.master_info_label)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Новая", "В работе", "Ожидает запчастей", "Завершена"])
        self.report_edit = QTextEdit()
        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)

        detail_layout.addRow("Статус:", self.status_combo)
        detail_layout.addRow("Отчёт о выполненной работе:", self.report_edit)
        detail_layout.addRow(QLabel("История переписки:"))
        detail_layout.addRow(self.history_view)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        parts_btn = QPushButton("Отправить на заказ запчастей")
        parts_btn.clicked.connect(self.send_for_parts)
        status_btn = QPushButton("Сохранить статус")
        status_btn.clicked.connect(self.save_status)
        report_btn = QPushButton("Сохранить отчёт")
        report_btn.clicked.connect(self.save_report)
        attach_btn = QPushButton("Прикрепить файл (фото)")
        attach_btn.clicked.connect(self.attach_file)
        btn_row.addWidget(parts_btn)
        btn_row.addWidget(status_btn)
        btn_row.addWidget(report_btn)
        btn_row.addWidget(attach_btn)

        detail_layout.addRow(btn_row)
        detail_group.setLayout(detail_layout)

        main_layout.addWidget(detail_group)
        self.setLayout(main_layout)

    def set_master(self) -> None:
        self.master_name = self.master_edit.text().strip()
        if not self.master_name:
            QMessageBox.warning(self, "Ошибка", "Введите имя мастера.")
            return
        self.master_id = get_user_id_by_name_or_login(self.master_name)
        if self.master_id is None:
            QMessageBox.warning(self, "Ошибка", "Мастер с таким именем/логином не найден в БД.")
            return
        self.reload_table()

    def reload_table(self) -> None:
        if not self.master_id:
            self.table.setRowCount(0)
            return
        tickets = fetch_requests_for_master(self.master_id)
        self.requests = tickets
        self.table.setRowCount(0)
        for t in tickets:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(t["request_id"])))
            self.table.setItem(row, 1, QTableWidgetItem(t["equipment_type"]))
            self.table.setItem(row, 2, QTableWidgetItem(t["equipment_model"]))
            self.table.setItem(row, 3, QTableWidgetItem(t["status"]))
            self.table.setItem(row, 4, QTableWidgetItem(t["priority"]))
        self.current_request = None
        self.update_details()

    def _get_selected_request(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        if row >= len(self.requests):
            return None
        return self.requests[row]

    def on_ticket_selected(self, row: int, column: int) -> None:
        _ = row, column
        self.current_request = self._get_selected_request()
        self.update_details()

    def update_details(self) -> None:
        t = self.current_request
        if not t:
            self.master_info_label.setText("Заявка не выбрана.")
            self.report_edit.clear()
            self.history_view.clear()
            return
        self.master_info_label.setText(
            f"Заявка ID {t['request_id']}: {t['equipment_type']} {t['equipment_model']}, "
            f"клиент {t['client_lastname']} {t['client_firstname']}"
        )
        idx = self.status_combo.findText(t["status"])
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.report_edit.setPlainText(t.get("report") or "")

        comments = fetch_request_comments(t["request_id"])
        history_lines: List[str] = []
        for c in comments:
            author = f"{c['lastname']} {c['firstname']}".strip()
            history_lines.append(f"[{c['created_at']}] {c['role_name']} {author}: {c['message']}")
        self.history_view.setPlainText("\n".join(history_lines))

    def send_for_parts(self) -> None:
        t = self.current_request
        if not t:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку.")
            return
        set_request_requires_parts(t["request_id"], True)
        if self.master_id:
            add_comment(
                t["request_id"],
                self.master_id,
                "Отправлена заявка на заказ недостающих запчастей.",
            )
        QMessageBox.information(
            self,
            "Информация",
            "Информация о необходимости заказа запчастей сохранена.",
        )
        self.update_details()

    def save_status(self) -> None:
        t = self.current_request
        if not t:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку.")
            return
        new_status = self.status_combo.currentText()
        status_id = get_status_id(new_status)
        notify = new_status.lower() in ("завершена", "выполнена", "готова к выдаче")
        update_request_status_and_report(
            request_id=t["request_id"],
            status_id=status_id,
            report=None,
            notify_client=notify,
        )
        if self.master_id:
            add_comment(
                t["request_id"],
                self.master_id,
                f"Статус изменён на '{new_status}'.",
            )
        QMessageBox.information(self, "Успех", "Статус заявки обновлён.")
        self.reload_table()

    def save_report(self) -> None:
        t = self.current_request
        if not t:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку.")
            return
        report = self.report_edit.toPlainText().strip()
        if not report:
            QMessageBox.warning(self, "Ошибка", "Отчёт не может быть пустым.")
            return
        # сохраняем отчёт и отмечаем, что клиента нужно оповестить
        status_id = get_status_id(t["status"])
        update_request_status_and_report(
            request_id=t["request_id"],
            status_id=status_id,
            report=report,
            notify_client=True,
        )
        if self.master_id:
            add_comment(
                t["request_id"],
                self.master_id,
                f"Добавлен отчёт о выполненной работе: {report}",
            )
        QMessageBox.information(self, "Успех", "Отчёт сохранён.")
        self.update_details()

    def attach_file(self) -> None:
        t = self.current_request
        if not t:
            QMessageBox.warning(self, "Ошибка", "Выберите заявку.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл (фото)")
        if not path:
            return
        desc = "Фото с места ремонта"
        if self.master_id:
            db_add_attachment(t["request_id"], self.master_id, path, desc)
            add_comment(
                t["request_id"],
                self.master_id,
                f"К заявке прикреплено фото: {path}",
            )
        QMessageBox.information(self, "Успех", "Файл прикреплён.")
        self.update_details()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Учёт заявок на ремонт оргтехники")
        self.resize(1150, 720)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setTabPosition(QTabWidget.North)
        tabs.addTab(ClientTab(), "Клиент")
        tabs.addTab(OperatorTab(), "Оператор")
        tabs.addTab(MasterTab(), "Мастер")

        self.setCentralWidget(tabs)

        # Общий стиль приложения
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f5f7fb;
            }
            QTabWidget::pane {
                border-top: 2px solid #cccccc;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #e0e4f5;
                border: 1px solid #b8c0e0;
                padding: 6px 14px;
                margin-right: 2px;
                border-bottom-color: #b8c0e0;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom-color: #ffffff;
                font-weight: bold;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #c0c8e0;
                border-radius: 6px;
                margin-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }
            QLabel {
                font-size: 12px;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #fbfcff;
                border: 1px solid #c0c8e0;
                border-radius: 4px;
                padding: 3px;
            }
            QPushButton {
                background-color: #4b6ef5;
                color: white;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3d5ed8;
            }
            QPushButton:pressed {
                background-color: #324fad;
            }
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d7e5;
            }
            QHeaderView::section {
                background-color: #e5e9f5;
                padding: 4px;
                border: 1px solid #c0c8e0;
            }
            """
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


