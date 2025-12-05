-- SQL-скрипт для локального развёртывания БД под проект
-- Адаптирован для MySQL / MariaDB

CREATE DATABASE IF NOT EXISTS service_center
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE service_center;

-- ===== Справочники =====

CREATE TABLE IF NOT EXISTS roles (
  role_id   INT PRIMARY KEY AUTO_INCREMENT,
  role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
  user_id   INT PRIMARY KEY AUTO_INCREMENT,
  lastname  VARCHAR(100) NOT NULL,
  firstname VARCHAR(100) NOT NULL,
  surname   VARCHAR(100) NOT NULL,
  phone     VARCHAR(20)  NOT NULL,
  login     VARCHAR(50)  NOT NULL UNIQUE,
  password  VARCHAR(255) NOT NULL,
  role_id   INT          NOT NULL,
  CONSTRAINT fk_users_role
    FOREIGN KEY (role_id) REFERENCES roles (role_id)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS equipment_types (
  type_id   INT PRIMARY KEY AUTO_INCREMENT,
  type_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS equipment (
  equipment_id INT PRIMARY KEY AUTO_INCREMENT,
  type_id      INT          NOT NULL,
  model        VARCHAR(100) NOT NULL,
  CONSTRAINT fk_equipment_type
    FOREIGN KEY (type_id) REFERENCES equipment_types (type_id)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS request_statuses (
  status_id   INT PRIMARY KEY AUTO_INCREMENT,
  status_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS parts (
  part_id   INT PRIMARY KEY AUTO_INCREMENT,
  part_name VARCHAR(100) NOT NULL UNIQUE
);

-- ===== Основные сущности =====

CREATE TABLE IF NOT EXISTS requests (
  request_id          INT PRIMARY KEY AUTO_INCREMENT,
  start_date          DATE        NOT NULL,
  equipment_id        INT         NOT NULL,
  problem_description TEXT        NOT NULL,
  status_id           INT         NOT NULL,
  completion_date     DATE        NULL,
  master_id           INT         NULL,
  client_id           INT         NOT NULL,
  notify_client       TINYINT(1)  NOT NULL DEFAULT 0,
  report              TEXT        NULL,
  requires_parts      TINYINT(1)  NOT NULL DEFAULT 0,
  -- дополнительные поля для оператора/аналитики
  priority            VARCHAR(20)  NOT NULL DEFAULT 'Средний',
  ticket_type         VARCHAR(100) NOT NULL DEFAULT 'Стандартная',
  operator_group      VARCHAR(100) NULL,
  responsible_operator VARCHAR(100) NULL,
  observers_text      TEXT         NULL,
  CONSTRAINT fk_requests_equipment
    FOREIGN KEY (equipment_id) REFERENCES equipment (equipment_id)
      ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_requests_status
    FOREIGN KEY (status_id) REFERENCES request_statuses (status_id)
      ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_requests_master
    FOREIGN KEY (master_id) REFERENCES users (user_id)
      ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT fk_requests_client
    FOREIGN KEY (client_id) REFERENCES users (user_id)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Связь заявки и запчастей
CREATE TABLE IF NOT EXISTS request_parts (
  request_id INT NOT NULL,
  part_id    INT NOT NULL,
  quantity   INT NOT NULL DEFAULT 1,
  PRIMARY KEY (request_id, part_id),
  CONSTRAINT fk_reqparts_request
    FOREIGN KEY (request_id) REFERENCES requests (request_id)
      ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_reqparts_part
    FOREIGN KEY (part_id) REFERENCES parts (part_id)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

-- История комментариев по заявкам (от любого пользователя)
CREATE TABLE IF NOT EXISTS comments (
  comment_id INT PRIMARY KEY AUTO_INCREMENT,
  message    TEXT        NOT NULL,
  user_id    INT         NOT NULL,
  request_id INT         NOT NULL,
  created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_comments_user
    FOREIGN KEY (user_id) REFERENCES users (user_id)
      ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_comments_request
    FOREIGN KEY (request_id) REFERENCES requests (request_id)
      ON UPDATE CASCADE ON DELETE CASCADE
);

-- Вложения (файлы/фото), которые пользователь или мастер прикрепляет к заявке
CREATE TABLE IF NOT EXISTS attachments (
  attachment_id INT PRIMARY KEY AUTO_INCREMENT,
  request_id    INT          NOT NULL,
  user_id       INT          NULL,
  file_path     VARCHAR(255) NOT NULL,
  description   VARCHAR(255) NULL,
  uploaded_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_attachments_request
    FOREIGN KEY (request_id) REFERENCES requests (request_id)
      ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_attachments_user
    FOREIGN KEY (user_id) REFERENCES users (user_id)
      ON UPDATE CASCADE ON DELETE SET NULL
);

-- ===== Первичное наполнение справочников =====

INSERT INTO roles (role_name) VALUES
  ('Менеджер'),
  ('Мастер'),
  ('Оператор'),
  ('Заказчик')
ON DUPLICATE KEY UPDATE role_name = VALUES(role_name);

INSERT INTO equipment_types (type_name) VALUES
  ('Компьютер'),
  ('Ноутбук'),
  ('Принтер')
ON DUPLICATE KEY UPDATE type_name = VALUES(type_name);

INSERT INTO request_statuses (status_name) VALUES
  ('Новая заявка'),
  ('В процессе ремонта'),
  ('Готова к выдаче')
ON DUPLICATE KEY UPDATE status_name = VALUES(status_name);

-- Пользователи (операторы, мастера, заказчики)
INSERT INTO users (lastname, firstname, surname, phone, login, password, role_id) VALUES
  ('Носов',     'Иван',      'Михайлович',   '89210563128', 'login1',  'pass1',  1),
  ('Ильин',     'Александр', 'Андреевич',    '89535078985', 'login2',  'pass2',  2),
  ('Никифоров', 'Иван',      'Дмитриевич',   '89210673849', 'login3',  'pass3',  2),
  ('Елисеев',   'Артём',     'Леонидович',   '89990563748', 'login4',  'pass4',  3),
  ('Титов',     'Сергей',    'Кириллович',   '89994563847', 'login5',  'pass5',  3),
  ('Григорьев', 'Семён',     'Викторович',   '89219567849', 'login11', 'pass11', 4),
  ('Сорокин',   'Дмитрий',   'Ильич',        '89219567841', 'login12', 'pass12', 4),
  ('Белоусов',  'Егор',      'Ярославович',  '89219567842', 'login13', 'pass13', 4),
  ('Суслов',    'Михаил',    'Александрович','89219567843', 'login14', 'pass14', 4),
  ('Васильев',  'Вячеслав',  'Александрович','89219567844', 'login15', 'pass15', 2)
ON DUPLICATE KEY UPDATE phone = VALUES(phone);

INSERT INTO equipment (type_id, model) VALUES
  (1, 'DEXP Aquilon O286'),
  (1, 'DEXP Atlas H388'),
  (2, 'MSI GF76 Katana 11UC-879XRU черный'),
  (2, 'MSI Modern 15 B12M-211RU черный'),
  (3, 'HP LaserJet Pro M404dn')
ON DUPLICATE KEY UPDATE model = VALUES(model);

-- Пример заявок: ID будут присвоены автоматически
INSERT INTO requests (start_date, equipment_id, problem_description, status_id, completion_date, master_id, client_id)
VALUES
  ('2023-06-06', 1, 'Перестал работать',       2, NULL, 2, 7),
  ('2023-05-05', 2, 'Перестал работать',       2, NULL, 3, 8),
  ('2022-07-07', 3, 'Выключается',             3, '2023-01-01', 3, 9),
  ('2023-08-02', 4, 'Выключается',             1, NULL, NULL, 8),
  ('2023-08-02', 5, 'Перестала включаться',    1, NULL, NULL, 9);

INSERT INTO comments (message, user_id, request_id)
VALUES
  ('Интересно...',                 2, 1),
  ('Будем разбираться!',           3, 2),
  ('Сделаем всё на высшем уровне!',3, 3);


