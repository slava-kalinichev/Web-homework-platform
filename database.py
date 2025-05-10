import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Путь к базе данных
DB_PATH = Path('C:/Users/Slava/Documents/Python/lmsDataBase')


def get_db_connection():
    """Создает и возвращает соединение с базой данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def register_user(last_name, first_name, middle_name, role, login, password):
    """Регистрация нового пользователя"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Проверка существования логина
            cursor.execute('SELECT Login FROM Accounts WHERE Login = ?', (login,))
            if cursor.fetchone():
                return None

            # Создание аккаунта
            cursor.execute(
                'INSERT INTO Accounts (Login, SecretPass, Status) VALUES (?, ?, ?)',
                (login, password, 'active')
            )

            # Создание записи в соответствующей таблице
            if role == 'student':
                cursor.execute(
                    'INSERT INTO Students (Login, LastName, FirstName, MiddleName) VALUES (?, ?, ?, ?)',
                    (login, last_name, first_name, middle_name)
                )
                user_id = cursor.lastrowid
            else:
                cursor.execute(
                    'INSERT INTO Teachers (Login, LastName, FirstName, MiddleName) VALUES (?, ?, ?, ?)',
                    (login, last_name, first_name, middle_name)
                )
                user_id = cursor.lastrowid

            # Добавление роли
            cursor.execute(
                'INSERT INTO AccountsRole (Login, RoleID) VALUES (?, ?)',
                (login, role)
            )

            conn.commit()
            return user_id
        except sqlite3.Error as e:
            print(f"Ошибка регистрации пользователя: {e}")
            conn.rollback()
            return None

def authenticate_user(login, password):
    """Проверяет учетные данные пользователя"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Проверяем существование логина
        cursor.execute(
            'SELECT Login FROM Accounts WHERE Login = ?',
            (login,)
        )
        if not cursor.fetchone():
            return {'status': 'login_not_found'}

        # Проверяем пароль
        cursor.execute(
            'SELECT Login, SecretPass FROM Accounts WHERE Login = ? AND Status = "active"',
            (login,)
        )
        account = cursor.fetchone()

        if account and account['SecretPass'] == password:
            # Получаем роль пользователя
            cursor.execute(
                'SELECT RoleID FROM AccountsRole WHERE Login = ?',
                (login,)
            )
            role = cursor.fetchone()
            return {
                'status': 'success',
                'login': account['Login'],
                'role': role['RoleID'] if role else None
            }
        return {'status': 'wrong_password'}


def get_user_info(login):
    """Получает информацию о пользователе по логину"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Сначала проверяем роль
        cursor.execute(
            'SELECT RoleID FROM AccountsRole WHERE Login = ?',
            (login,)
        )
        role = cursor.fetchone()

        if not role:
            return None

        role = role['RoleID']

        if role == 'student':
            cursor.execute(
                'SELECT StudentID as id, LastName || " " || FirstName || " " || MiddleName as name FROM Students WHERE Login = ?',
                (login,)
            )
        else:
            cursor.execute(
                'SELECT TeacherID as id, LastName || " " || FirstName || " " || MiddleName as name FROM Teachers WHERE Login = ?',
                (login,)
            )

        user = cursor.fetchone()
        if user:
            return {'id': user['id'], 'name': user['name'], 'role': role}
        return None


def create_class(class_name, teacher_id, is_school_class):
    """Функция создания класса"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Получаем школу учителя (если есть)
            school = get_teacher_school(teacher_id)
            school_id = school['SchoolID'] if school else None

            # Юля школьных классов переименовываем конфликтующие персональные классы
            if is_school_class and school_id:
                rename_conflicting_classes(class_name, school_id)

            # Проверяем существование класса в школе или у учителя
            if is_class_name_exists_in_school(class_name, school_id, teacher_id):
                return False

            # Создаем класс
            cursor.execute('INSERT INTO Classes (ClassTitle) VALUES (?)', (class_name,))
            class_id = cursor.lastrowid

            # Добавляем в соответствующую таблицу
            if is_school_class:
                if school:
                    cursor.execute('INSERT INTO ClassesInSchools (ClassID, SchoolID) VALUES (?, ?)',
                                   (class_id, school['SchoolID']))
            else:
                cursor.execute('INSERT INTO MyClasses (ClassID, TeacherID) VALUES (?, ?)',
                               (class_id, teacher_id))

            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Ошибка создания класса: {e}")
            return False


def get_class_students(class_id):
    """Получает список учеников в конкретном классе по ID класса"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                s.StudentID as id, 
                s.LastName || ' ' || s.FirstName || ' ' || s.MiddleName as name,
                a.Login as login
            FROM Students s
            JOIN Accounts a ON s.Login = a.Login
            JOIN StudentInClasses sc ON s.StudentID = sc.StudentID
            WHERE sc.ClassID = ?
            ORDER BY s.LastName
        ''', (class_id,))
        return cursor.fetchall()


def create_task(subject_title, theme, teacher_id, class_id, deadline, task_text):
    """Создает новое задание с корректным дедлайном"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Получаем или создаем subject
            cursor.execute('SELECT SubjectID FROM Subjects WHERE SubjectTitle = ?', (subject_title,))
            subject = cursor.fetchone()

            if not subject:
                cursor.execute('INSERT INTO Subjects (SubjectTitle) VALUES (?)', (subject_title,))
                subject_id = cursor.lastrowid
            else:
                subject_id = subject['SubjectID']

            # Преобразуем дату из формата YYYY-MM-DD в Unix timestamp
            deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
            unix_timestamp = int(deadline_date.timestamp())

            cursor.execute('''
                INSERT INTO Tasks (Date, ClassID, TeacherID, SubjectID, Topic, Text)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (unix_timestamp, class_id, teacher_id, subject_id, theme, task_text))

            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Ошибка создания задания: {str(e)}")
            conn.rollback()
            return None


def get_teacher_classes_for_select(teacher_id):
    """Получает классы учителя для выпадающего списка с сортировкой"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.ClassID as id, c.ClassTitle as name
            FROM Classes c
            LEFT JOIN MyClasses mc ON c.ClassID = mc.ClassID AND mc.TeacherID = ?
            LEFT JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
            LEFT JOIN TeachersInSchools tis ON cis.SchoolID = tis.SchoolID AND tis.TeacherID = ?
            WHERE mc.TeacherID IS NOT NULL OR tis.TeacherID IS NOT NULL
            ORDER BY c.ClassTitle COLLATE NOCASE ASC
        ''', (teacher_id, teacher_id))
        return [dict(row) for row in cursor.fetchall()]


def is_deadline_passed(deadline_unix):
    """Проверяет, прошел ли дедлайн"""
    if not deadline_unix:
        return False
    deadline_date = datetime.fromtimestamp(int(deadline_unix))
    return datetime.now() > deadline_date


def get_teacher_id_by_login(login):
    """Получает ID учителя по логину"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT TeacherID FROM Teachers WHERE Login = ?', (login,))
        result = cursor.fetchone()
        return result['TeacherID'] if result else None


def submit_solution(student_id, task_id, solution_text, file_data=None, filename=None, mime_type=None):
    """Обновляет или создает решение задания"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            current_time = int(datetime.now().timestamp())

            # Проверяем дедлайн
            cursor.execute('SELECT Date FROM Tasks WHERE TaskID = ?', (task_id,))
            task = cursor.fetchone()
            if task and datetime.now().timestamp() > task['Date']:
                return False  # Дедлайн прошел

            # Проверяем существующее решение
            cursor.execute('''
                SELECT STID FROM StudentTasks
                WHERE StudentID = ? AND TaskID = ?
            ''', (student_id, task_id))
            exists = cursor.fetchone()

            if exists:
                # Обновляем существующее решение
                cursor.execute('''
                    UPDATE StudentTasks SET
                        Decision = ?,
                        Status = 'submitted',
                        Mark = NULL,
                        Comment = NULL,
                        DispatchDT = ?
                    WHERE StudentID = ? AND TaskID = ?
                ''', (solution_text, current_time, student_id, task_id))
                stid = exists['STID']

                # Удаляем старый файл, если есть
                cursor.execute('DELETE FROM SolutionFiles WHERE STID = ?', (stid,))
            else:
                # Создаем новое решение
                cursor.execute('''
                    INSERT INTO StudentTasks
                    (StudentID, TaskID, Decision, Status, DispatchDT)
                    VALUES (?, ?, ?, 'submitted', ?)
                ''', (student_id, task_id, solution_text, current_time))
                stid = cursor.lastrowid

            # Сохраняем файл, если он есть
            if file_data and filename:
                cursor.execute('''
                    INSERT INTO SolutionFiles (STID, FileName, FileData, MimeType)
                    VALUES (?, ?, ?, ?)
                ''', (stid, filename, file_data, mime_type))

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Ошибка при отправке решения: {e}")
            return False


def grade_solution_func(student_id, task_id, grade, comment):
    """Оценивает решение задания учителем"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            # Определяем статус на основе оценки
            status = 'graded' if grade != 'незачёт' else 'failed'

            cursor.execute('''
                UPDATE StudentTasks 
                SET Mark = ?, 
                    Comment = ?,
                    Status = ?
                WHERE StudentID = ? AND TaskID = ?
            ''', (grade, comment, status, student_id, task_id))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении оценки: {e}")
            return False


def get_task_details(task_id):
    """Получает детали задания с корректным дедлайном"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                t.TaskID as id,
                s.SubjectTitle as subject,
                t.Topic as theme,
                t.Text as text,
                t.Date as deadline_unix,
                (SELECT te.LastName || ' ' || te.FirstName || ' ' || te.MiddleName
                 FROM Teachers te WHERE te.TeacherID = t.TeacherID) as teacher,
                c.ClassTitle as class_name
            FROM Tasks t
            JOIN Subjects s ON t.SubjectID = s.SubjectID
            JOIN Classes c ON t.ClassID = c.ClassID
            WHERE t.TaskID = ?
        ''', (task_id,))
        task = cursor.fetchone()
        if task:
            task = dict(task)
            try:
                deadline_date = datetime.fromtimestamp(int(task['deadline_unix'])) - timedelta(days=1)
                task['deadline'] = deadline_date.strftime('%d.%m.%Y')
            except:
                task['deadline'] = "Нет даты"

            # Получаем информацию о файле
            cursor.execute('''
                SELECT FileName 
                FROM TaskFiles 
                WHERE TaskID = ?
            ''', (task_id,))
            file_info = cursor.fetchone()
            if file_info:
                task['file'] = dict(file_info)
        return task


def get_task_solutions(task_id):
    """Получает решения для задания с корректными датами"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                st.StudentID as student_id,
                s.LastName || ' ' || s.FirstName || ' ' || s.MiddleName as student_name,
                st.Decision as text,
                st.Mark as grade,
                st.Comment as comment,
                datetime(st.DispatchDT, 'unixepoch', 'localtime') as submission_date
            FROM StudentTasks st
            JOIN Students s ON st.StudentID = s.StudentID
            WHERE st.TaskID = ?
        ''', (task_id,))
        return cursor.fetchall()


def delete_class_by_id(class_id, teacher_id):
    """Удаляет класс по его ID с проверкой принадлежности учителю и очисткой всех связанных таблиц"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Проверяем принадлежность класса учителю
            cursor.execute('''
                SELECT 1 FROM (
                    SELECT c.ClassID 
                    FROM Classes c
                    JOIN MyClasses mc ON c.ClassID = mc.ClassID
                    WHERE mc.TeacherID = ? AND c.ClassID = ?

                    UNION

                    SELECT c.ClassID 
                    FROM Classes c
                    JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
                    JOIN TeachersInSchools tis ON cis.SchoolID = tis.SchoolID
                    WHERE tis.TeacherID = ? AND c.ClassID = ?
                ) AS valid_classes
            ''', (teacher_id, class_id, teacher_id, class_id))

            if not cursor.fetchone():
                return False  # Учитель не имеет прав на удаление этого класса

            # Удаляем связи с учениками
            cursor.execute('DELETE FROM StudentInClasses WHERE ClassID = ?', (class_id,))

            # Удаляем из таблицы школьных классов (если есть)
            cursor.execute('DELETE FROM ClassesInSchools WHERE ClassID = ?', (class_id,))

            # Удаляем из таблицы персональных классов (если есть)
            cursor.execute('DELETE FROM MyClasses WHERE ClassID = ?', (class_id,))

            # Удаляем задания класса
            cursor.execute('DELETE FROM Tasks WHERE ClassID = ?', (class_id,))

            # Удаляем сам класс
            cursor.execute('DELETE FROM Classes WHERE ClassID = ?', (class_id,))

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Ошибка при удалении класса: {e}")
            conn.rollback()
            return False


def delete_student_from_class(class_id, student_id):
    """Удаляет ученика из класса"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM StudentInClasses WHERE ClassID = ? AND StudentID = ?',
                (class_id, student_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False

def get_class_by_name(class_name):
    """Получает класс по имени"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ClassID as id, ClassTitle as name FROM Classes WHERE ClassTitle = ?', (class_name,))
        return cursor.fetchone()

def get_student_info(student_id):
    """Получает полную информацию об ученике"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                s.StudentID,
                s.LastName,
                s.FirstName,
                s.MiddleName,
                a.Login
            FROM Students s
            JOIN Accounts a ON s.Login = a.Login
            WHERE s.StudentID = ?
        ''', (student_id,))
        return cursor.fetchone()


def get_student_statistics(student_id):
    """Получает статистику ученика"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT t.TaskID) as total_tasks,
                SUM(CASE WHEN st.Status = 'graded' THEN 1 ELSE 0 END) as completed_tasks,
                AVG(CASE WHEN st.Mark IN ('2','3','4','5') THEN CAST(st.Mark AS REAL) ELSE NULL END) as average_grade
            FROM StudentInClasses sc
            JOIN Tasks t ON sc.ClassID = t.ClassID
            LEFT JOIN StudentTasks st ON t.TaskID = st.TaskID AND st.StudentID = ?
            WHERE sc.StudentID = ?
        ''', (student_id, student_id))
        stats = cursor.fetchone()

        return {
            'total_tasks': stats['total_tasks'] or 0,
            'completed_tasks': stats['completed_tasks'] or 0,
            'average_grade': round(stats['average_grade'], 1) if stats['average_grade'] else 0.0
        }

def get_solution_details(task_id, student_id):
    """Получает детали решения"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                st.StudentID as student_id,
                s.LastName || ' ' || s.FirstName || ' ' || s.MiddleName as student_name,
                st.Decision as text,
                st.Mark as grade,
                st.Comment as comment,
                strftime('%d.%m.%Y', t.Date, 'unixepoch') as submission_date
            FROM StudentTasks st
            JOIN Students s ON st.StudentID = s.StudentID
            JOIN Tasks t ON st.TaskID = t.TaskID
            WHERE st.TaskID = ? AND st.StudentID = ?
        ''', (task_id, student_id))
        return cursor.fetchone()


def get_student_tasks(student_id):
    """Получает список заданий для конкретного ученика с корректным дедлайном"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                t.TaskID as id,
                t.Date as deadline_unix,
                s.SubjectTitle as subject,
                t.Topic as theme,
                c.ClassTitle as class_name,
                t.Text as text,
                te.LastName || ' ' || SUBSTR(te.FirstName, 1, 1) || '.' as teacher_name,
                CASE 
                    WHEN st.STID IS NULL THEN 'not_submitted'
                    WHEN st.Status = 'submitted' AND st.Mark IS NULL THEN 'submitted'
                    WHEN st.Status = 'graded' THEN 'graded'
                    ELSE 'unknown'
                END as status,
                st.Mark as grade,
                st.Comment as comment
            FROM Tasks t
            JOIN Subjects s ON t.SubjectID = s.SubjectID
            JOIN Teachers te ON t.TeacherID = te.TeacherID
            JOIN Classes c ON t.ClassID = c.ClassID
            JOIN StudentInClasses sc ON t.ClassID = sc.ClassID
            LEFT JOIN StudentTasks st ON t.TaskID = st.TaskID AND st.StudentID = ?
            WHERE sc.StudentID = ?
            ORDER BY t.Date DESC
        ''', (student_id, student_id))

        tasks = []
        for task in cursor.fetchall():
            task_dict = dict(task)
            if task_dict['deadline_unix']:
                task_dict['deadline'] = (
                            datetime.fromtimestamp(task_dict['deadline_unix']) - timedelta(days=1)).strftime('%d.%m.%Y')
            else:
                task_dict['deadline'] = "Нет даты"
            tasks.append(task_dict)
        return tasks

def get_student_id_by_login(login):
    """Получает ID ученика по логину"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT StudentID FROM Students WHERE Login = ?', (login,))
        result = cursor.fetchone()
        return result['StudentID'] if result else None


def is_class_name_available(class_name, teacher_id=None):
    """Проверяет, свободно ли имя класса для данного учителя"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        if teacher_id is None:
            # Если teacher_id не указан, проверяем только глобальную уникальность
            cursor.execute('SELECT 1 FROM Classes WHERE ClassTitle = ?', (class_name,))
            return cursor.fetchone() is None

        # Получаем школу учителя (если есть)
        school = get_teacher_school(teacher_id)
        school_id = school['SchoolID'] if school else None

        return not is_class_name_exists_in_school(class_name, school_id, teacher_id)


def get_tasks_with_pending_solutions(teacher_id):
    """Получает задания с решениями на проверке, включая корректный deadline_unix"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                t.TaskID as id,
                s.SubjectTitle as subject,
                t.Topic as theme,
                t.Date as deadline_unix,
                c.ClassTitle as class_name,
                (SELECT COUNT(st.STID) 
                 FROM StudentTasks st 
                 WHERE st.TaskID = t.TaskID AND st.Status = 'submitted') as pending_count
            FROM Tasks t
            JOIN Subjects s ON t.SubjectID = s.SubjectID
            JOIN Classes c ON t.ClassID = c.ClassID
            WHERE t.TeacherID = ?
            ORDER BY t.Date DESC
        ''', (teacher_id,))

        tasks = []
        for task in cursor.fetchall():
            task_dict = dict(task)
            # Добавляем дату для отображения
            try:
                if task_dict['deadline_unix']:
                    if task_dict['deadline_unix']:
                        task_dict['date'] = (
                                    datetime.fromtimestamp(task_dict['deadline_unix']) - timedelta(days=1)).strftime(
                            '%d.%m.%Y')
                else:
                    task_dict['date'] = "Нет даты"
            except:
                task_dict['date'] = "Нет даты"

            tasks.append(task_dict)

        return tasks


def delete_task_func(task_id):
    """Удаляет задание и все связанные решения"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            # Сначала удаляям решения
            cursor.execute('DELETE FROM StudentTasks WHERE TaskID = ?', (task_id,))
            # Затем удаляем само задание
            cursor.execute('DELETE FROM Tasks WHERE TaskID = ?', (task_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Ошибка при удалении задания: {e}")
            conn.rollback()
            return False

def get_school_by_code(school_code):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Schools WHERE SchoolCode = ?', (school_code,))
        return cursor.fetchone()

def get_teacher_info_by_id(teacher_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT LastName, FirstName, MiddleName 
            FROM Teachers 
            WHERE TeacherID = ?
        ''', (teacher_id,))
        return cursor.fetchone()

def get_teacher_school(teacher_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.SchoolID, s.SchoolName 
            FROM TeachersInSchools tis
            JOIN Schools s ON tis.SchoolID = s.SchoolID
            WHERE tis.TeacherID = ?
        ''', (teacher_id,))
        return cursor.fetchone()


def create_my_class(class_name, teacher_id):
    """Создает персональный класс с проверкой уникальности имени"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Получаем школу учителя (если есть)
            school = get_teacher_school(teacher_id)
            school_id = school['SchoolID'] if school else None

            # Проверяем существование класса в школе или у учителя
            if is_class_name_exists_in_school(class_name, school_id, teacher_id):
                return False

            # Создаем новый класс
            cursor.execute('INSERT INTO Classes (ClassTitle) VALUES (?)', (class_name,))
            class_id = cursor.lastrowid
            cursor.execute('INSERT INTO MyClasses (ClassID, TeacherID) VALUES (?, ?)',
                           (class_id, teacher_id))

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Ошибка создания персонального класса: {e}")
            conn.rollback()
            return False


def add_student_to_class(class_id, student_login, is_school_class_value=False):
    """Добавляет ученика в класс с правильной логикой проверок"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # 1. Проверяем существует ли ученик
            cursor.execute('SELECT StudentID FROM Students WHERE Login = ?', (student_login,))
            student = cursor.fetchone()

            if not student:
                return False, 'Ученик с таким логином не найден'

            student_id = student['StudentID']

            # 2. Проверяем не состоит ли уже в этом классе
            cursor.execute(
                'SELECT 1 FROM StudentInClasses WHERE ClassID = ? AND StudentID = ?',
                (class_id, student_id)
            )
            if cursor.fetchone():
                return False, 'Ученик уже состоит в этом классе'

            # 3. Для ШКОЛЬНЫХ классов проверяем не состоит ли в другом школьном классе
            if is_school_class_value:
                cursor.execute('''
                    SELECT 1 FROM StudentInClasses sc
                    JOIN ClassesInSchools cis ON sc.ClassID = cis.ClassID
                    WHERE sc.StudentID = ? AND sc.ClassID != ?
                ''', (student_id, class_id))

                if cursor.fetchone():
                    return False, 'Ученик уже состоит в другом школьном классе'

            # Если все проверки пройдены, добавляем в класс
            cursor.execute(
                'INSERT INTO StudentInClasses (ClassID, StudentID) VALUES (?, ?)',
                (class_id, student_id)
            )
            conn.commit()
            return True, 'Ученик успешно добавлен'

        except sqlite3.Error as e:
            print(f"Ошибка при добавлении ученика: {e}")
            conn.rollback()
            return False, 'Ошибка при добавлении ученика'


def is_school_class(class_id):
    """Проверяет, является ли класс школьным"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM ClassesInSchools WHERE ClassID = ?', (class_id,))
        return cursor.fetchone() is not None

def get_school_classes(teacher_id):
    """Получает только школьные классы этого учителя с сортировкой"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.ClassID as id, c.ClassTitle as name
            FROM Classes c
            JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
            JOIN TeachersInSchools tis ON cis.SchoolID = tis.SchoolID
            WHERE tis.TeacherID = ?
            ORDER BY c.ClassTitle COLLATE NOCASE ASC
        ''', (teacher_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_my_classes(teacher_id):
    """Получает только персональные классы этого учителя с сортировкой"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.ClassID as id, c.ClassTitle as name
            FROM Classes c
            JOIN MyClasses mc ON c.ClassID = mc.ClassID
            WHERE mc.TeacherID = ?
            ORDER BY c.ClassTitle COLLATE NOCASE ASC
        ''', (teacher_id,))
        return [dict(row) for row in cursor.fetchall()]

def send_class_invitation(class_id, student_login, teacher_id, is_school_class_value):
    """Отправляет заявку на вступление в класс с проверками"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Получаем ID ученика
            cursor.execute('SELECT StudentID FROM Students WHERE Login = ?', (student_login,))
            student = cursor.fetchone()
            if not student:
                return False, 'Ученик с таким логином не найден'

            student_id = student['StudentID']

            # Проверяем, не состоит ли уже в этом классе
            cursor.execute('''
                SELECT 1 FROM StudentInClasses 
                WHERE ClassID = ? AND StudentID = ?
            ''', (class_id, student_id))

            if cursor.fetchone():
                return False, 'Ученик уже состоит в этом классе'

            # Проверяем, не отправлялась ли уже заявка
            if check_invitation_exists(class_id, student_login):
                return False, 'Заявка этому ученику уже отправлена'

            if is_school_class_value:
                # Для школьных классов проверяем не состоит ли в другом школьном классе
                cursor.execute('''
                    SELECT 1 FROM StudentInClasses sc
                    JOIN ClassesInSchools cis ON sc.ClassID = cis.ClassID
                    WHERE sc.StudentID = ? AND sc.ClassID != ?
                ''', (student_id, class_id))

                if cursor.fetchone():
                    return False, 'Ученик уже состоит в другом школьном классе'

            # Создаем заявку
            current_time = int(datetime.now().timestamp())
            cursor.execute('''
                INSERT INTO ClassInvitations 
                (ClassID, StudentID, TeacherID, Status, CreatedAt)
                VALUES (?, ?, ?, 'pending', ?)
            ''', (class_id, student_id, teacher_id, current_time))

            conn.commit()
            return True, 'Заявка отправлена'
        except sqlite3.Error as e:
            print(f"Ошибка при отправке заявки: {e}")
            return False, 'Ошибка при отправке заявки'

def get_pending_invitations(student_id):
    """Получает pending заявки для ученика с информацией о классе и учителе"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                ci.InvitationID,
                c.ClassTitle as class_name,
                t.LastName || ' ' || t.FirstName || ' ' || t.MiddleName as teacher_name,
                CASE 
                    WHEN EXISTS (SELECT 1 FROM ClassesInSchools WHERE ClassID = c.ClassID) 
                    THEN 'школьный' 
                    ELSE 'персональный' 
                END as class_type
            FROM ClassInvitations ci
            JOIN Classes c ON ci.ClassID = c.ClassID
            JOIN Teachers t ON ci.TeacherID = t.TeacherID
            WHERE ci.StudentID = ? AND ci.Status = 'pending'
            ORDER BY ci.CreatedAt DESC
        ''', (student_id,))
        return cursor.fetchall()

def process_invitation_func(invitation_id, action):
    """Обрабатывает заявку (принимает/отклоняет) с автоматическим удалением из других школьных классов"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            current_time = int(datetime.now().timestamp())

            # Получаем полную информацию о заявке
            cursor.execute('''
                SELECT ci.ClassID, ci.StudentID, ci.TeacherID, 
                       c.ClassTitle, s.LastName, s.FirstName,
                       EXISTS(SELECT 1 FROM ClassesInSchools WHERE ClassID = ci.ClassID) AS is_school_class
                FROM ClassInvitations ci
                JOIN Classes c ON ci.ClassID = c.ClassID
                JOIN Students s ON ci.StudentID = s.StudentID
                WHERE ci.InvitationID = ?
            ''', (invitation_id,))
            invitation = cursor.fetchone()

            if not invitation:
                return False, 'Заявка не найдена'

            if action == 'accept':
                # Для школьных классов - сначала удаляем из всех других школьных классов
                if invitation['is_school_class']:
                    cursor.execute('''
                        DELETE FROM StudentInClasses
                        WHERE StudentID = ? AND ClassID IN (
                            SELECT ClassID FROM ClassesInSchools
                            WHERE ClassID != ?
                        )
                    ''', (invitation['StudentID'], invitation['ClassID']))

                # Добавляем в новый класс
                cursor.execute('''
                    INSERT OR IGNORE INTO StudentInClasses (ClassID, StudentID)
                    VALUES (?, ?)
                ''', (invitation['ClassID'], invitation['StudentID']))

            # Обновляем статус заявки
            cursor.execute('''
                UPDATE ClassInvitations 
                SET Status = ?, UpdatedAt = ?
                WHERE InvitationID = ?
            ''', ('accepted' if action == 'accept' else 'rejected',
                 current_time, invitation_id))

            conn.commit()
            return True, {
                'class_name': invitation['ClassTitle'],
                'student_name': f"{invitation['LastName']} {invitation['FirstName']}",
                'status': 'accepted' if action == 'accept' else 'rejected',
                'teacher_id': invitation['TeacherID']
            }
        except sqlite3.Error as e:
            print(f"Ошибка при обработке заявки: {e}")
            return False, 'Ошибка при обработке заявки'


def check_invitation_exists(class_id, student_login):
    """Проверяет, есть ли уже pending заявка для этого ученика в классе"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM ClassInvitations ci
            JOIN Students s ON ci.StudentID = s.StudentID
            WHERE ci.ClassID = ? AND s.Login = ? AND ci.Status = 'pending'
        ''', (class_id, student_login))
        return cursor.fetchone() is not None


def is_class_name_exists_in_school(class_name, school_id=None, teacher_id=None):
    """Проверяет, существует ли класс с таким именем в школе или у учителя"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Проверка школьных классов в конкретной школе
        if school_id:
            cursor.execute('''
                SELECT 1 FROM Classes c
                JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
                WHERE c.ClassTitle = ? AND cis.SchoolID = ?
            ''', (class_name, school_id))
            if cursor.fetchone():
                return True

        # Проверка персональных классов конкретного учителя
        if teacher_id:
            cursor.execute('''
                SELECT 1 FROM Classes c
                JOIN MyClasses mc ON c.ClassID = mc.ClassID
                WHERE c.ClassTitle = ? AND mc.TeacherID = ?
            ''', (class_name, teacher_id))
            if cursor.fetchone():
                return True

        return False


def rename_conflicting_classes(class_name, school_id):
    """Переименовывает конфликтующие персональные классы в школе"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Находим все персональные классы в школе с таким же именем
            cursor.execute('''
                SELECT c.ClassID, c.ClassTitle 
                FROM Classes c
                JOIN MyClasses mc ON c.ClassID = mc.ClassID
                JOIN TeachersInSchools tis ON mc.TeacherID = tis.TeacherID
                WHERE c.ClassTitle = ? AND tis.SchoolID = ?
            ''', (class_name, school_id))

            conflicting_classes = cursor.fetchall()

            # Переименовываем каждый конфликтующий класс
            for class_info in conflicting_classes:
                new_name = f"{class_info['ClassTitle']} (личный)"
                cursor.execute('''
                    UPDATE Classes SET ClassTitle = ? WHERE ClassID = ?
                ''', (new_name, class_info['ClassID']))

            conn.commit()
            return len(conflicting_classes)
        except sqlite3.Error as e:
            print(f"Ошибка при переименовании классов: {e}")
            conn.rollback()
            return 0

def get_class_teacher(class_id):
    """Получает учителя-владельца класса"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.TeacherID, t.LastName, t.FirstName, t.MiddleName 
            FROM Teachers t
            JOIN MyClasses mc ON t.TeacherID = mc.TeacherID
            WHERE mc.ClassID = ?
        ''', (class_id,))
        return cursor.fetchone()


def get_student_class_stats(student_id, class_id):
    """Получает статистику ученика по конкретному классу"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(t.TaskID) as total_tasks,
                SUM(CASE WHEN st.Status = 'graded' THEN 1 ELSE 0 END) as completed_tasks,
                SUM(CASE WHEN st.Status = 'failed' OR (st.Status IS NULL AND t.Date < strftime('%s', 'now')) THEN 1 ELSE 0 END) as missed_tasks,
                AVG(CASE WHEN st.Mark IN ('2','3','4','5') THEN CAST(st.Mark AS REAL) ELSE NULL END) as average_grade
            FROM Tasks t
            LEFT JOIN StudentTasks st ON t.TaskID = st.TaskID AND st.StudentID = ?
            WHERE t.ClassID = ?
        ''', (student_id, class_id))
        stats = cursor.fetchone()

        return {
            'total_tasks': stats['total_tasks'] or 0,
            'completed_tasks': stats['completed_tasks'] or 0,
            'missed_tasks': stats['missed_tasks'] or 0,
            'average_grade': stats['average_grade'] if stats['average_grade'] is not None else 0
        }


def create_task_with_file(subject_title, theme, teacher_id, class_id, deadline,
                          task_text, file_data, filename, mime_type):
    """Создает новое задание с прикрепленным файлом"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # Добавляем приписку о файле к тексту задания
            task_text_with_note = f"{task_text} (прикреплён файл)"

            # Получаем или создаем subject
            cursor.execute('SELECT SubjectID FROM Subjects WHERE SubjectTitle = ?', (subject_title,))
            subject = cursor.fetchone()

            if not subject:
                cursor.execute('INSERT INTO Subjects (SubjectTitle) VALUES (?)', (subject_title,))
                subject_id = cursor.lastrowid
            else:
                subject_id = subject['SubjectID']

            # Преобразуем дату из формата YYYY-MM-DD в Unix timestamp
            deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
            unix_timestamp = int(deadline_date.timestamp())

            # Создаем задание
            cursor.execute('''
                INSERT INTO Tasks (Date, ClassID, TeacherID, SubjectID, Topic, Text)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (unix_timestamp, class_id, teacher_id, subject_id, theme, task_text_with_note))

            task_id = cursor.lastrowid

            # Сохраняем файл
            if file_data and filename:
                cursor.execute('''
                    INSERT INTO TaskFiles (TaskID, FileName, FileData, MimeType)
                    VALUES (?, ?, ?, ?)
                ''', (task_id, filename, file_data, mime_type))

            conn.commit()
            return task_id
        except Exception as e:
            print(f"Ошибка создания задания с файлом: {str(e)}")
            conn.rollback()
            return None


def get_task_file(task_id):
    """Получает прикрепленный файл задания"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT FileID, FileName, FileData, MimeType 
            FROM TaskFiles 
            WHERE TaskID = ?
        ''', (task_id,))
        return cursor.fetchone()


def save_solution_file(stid, filename, file_data, mime_type):
    """Сохраняет файл решения в базу данных"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO SolutionFiles (STID, FileName, FileData, MimeType)
                VALUES (?, ?, ?, ?)
            ''', (stid, filename, file_data, mime_type))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Ошибка сохранения файла решения: {e}")
            return None


def get_solution_file(stid):
    """Получает файл решения по ID записи StudentTasks"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT FileID, FileName, FileData, MimeType 
            FROM SolutionFiles 
            WHERE STID = ?
        ''', (stid,))
        return cursor.fetchone()

def get_stid_by_solution(task_id, student_id):
    """Получает STID по ID задания и ID ученика"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT STID FROM StudentTasks
            WHERE TaskID = ? AND StudentID = ?
        ''', (task_id, student_id))
        result = cursor.fetchone()
        return result['STID'] if result else None


def leave_school(teacher_id):
    """Удаляет учителя из школы и все его задания для школьных классов"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # 1. Получаем ID школы учителя
            cursor.execute('''
                SELECT SchoolID FROM TeachersInSchools 
                WHERE TeacherID = ?
            ''', (teacher_id,))
            school = cursor.fetchone()

            if not school:
                return False, "Учитель не состоит ни в одной школе"

            school_id = school['SchoolID']

            # 2. Удаляем все задания учителя для школьных классов
            cursor.execute('''
                DELETE FROM Tasks 
                WHERE TeacherID = ? AND ClassID IN (
                    SELECT ClassID FROM ClassesInSchools 
                    WHERE SchoolID = ?
                )
            ''', (teacher_id, school_id))

            # 3. Удаляем учителя из школы
            cursor.execute('''
                DELETE FROM TeachersInSchools 
                WHERE TeacherID = ?
            ''', (teacher_id,))

            conn.commit()
            return True, "Учитель успешно покинул школу"
        except sqlite3.Error as e:
            conn.rollback()
            return False, f"Ошибка при выходе из школы: {str(e)}"

def join_school(teacher_id, school_code):
    """Добавляет учителя в школу по коду доступа"""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()

            # 1. Проверяем существование школы с таким кодом
            cursor.execute('''
                SELECT SchoolID FROM Schools 
                WHERE SchoolCode = ?
            ''', (school_code,))
            school = cursor.fetchone()

            if not school:
                return False, "Несуществующий код доступа школы"

            school_id = school['SchoolID']

            # 2. Если учитель уже в какой-то школе - выходим из нее
            cursor.execute('''
                SELECT SchoolID FROM TeachersInSchools 
                WHERE TeacherID = ?
            ''', (teacher_id,))
            current_school = cursor.fetchone()

            if current_school:
                # Удаляем все задания учителя для школьных классов
                cursor.execute('''
                    DELETE FROM Tasks 
                    WHERE TeacherID = ? AND ClassID IN (
                        SELECT ClassID FROM ClassesInSchools 
                        WHERE SchoolID = ?
                    )
                ''', (teacher_id, current_school['SchoolID']))

                # Удаляем учителя из старой школы
                cursor.execute('''
                    DELETE FROM TeachersInSchools 
                    WHERE TeacherID = ?
                ''', (teacher_id,))

            # 3. Добавляем учителя в новую школу
            cursor.execute('''
                INSERT INTO TeachersInSchools (TeacherID, SchoolID)
                VALUES (?, ?)
            ''', (teacher_id, school_id))

            conn.commit()
            return True, "Учитель успешно добавлен в школу"
        except sqlite3.Error as e:
            conn.rollback()
            return False, f"Ошибка при присоединении к школе: {str(e)}"


def get_class_by_name_and_teacher(class_name, teacher_id):
    """Получает класс по имени с проверкой принадлежности учителю"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.ClassID as id, c.ClassTitle as name 
            FROM Classes c
            LEFT JOIN MyClasses mc ON c.ClassID = mc.ClassID
            LEFT JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
            LEFT JOIN TeachersInSchools tis ON cis.SchoolID = tis.SchoolID
            WHERE c.ClassTitle = ? AND (mc.TeacherID = ? OR tis.TeacherID = ?)
        ''', (class_name, teacher_id, teacher_id))
        return cursor.fetchone()


def get_class_by_id_and_teacher(class_id, teacher_id):
    """Получает класс по ID с проверкой принадлежности учителю"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.ClassID as id, c.ClassTitle as name 
            FROM Classes c
            LEFT JOIN MyClasses mc ON c.ClassID = mc.ClassID
            LEFT JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
            LEFT JOIN TeachersInSchools tis ON cis.SchoolID = tis.SchoolID
            WHERE c.ClassID = ? AND (mc.TeacherID = ? OR tis.TeacherID = ?)
        ''', (class_id, teacher_id, teacher_id))
        return cursor.fetchone()