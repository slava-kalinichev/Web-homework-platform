from database import (
    get_db_connection,
    get_student_id_by_login,
    get_teacher_id_by_login,
    get_student_tasks,
)


def get_new_submissions(teacher_login: str) -> list[str] | bool:
    """Получает все непроверенные работы для учителя"""
    teacher_id = get_teacher_id_by_login(teacher_login)
    if not teacher_id:
        return False

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.StudentID, s.LastName, s.FirstName, t.TaskID, t.Topic, sub.SubjectTitle, c.ClassTitle
            FROM StudentTasks st
            JOIN Tasks t ON st.TaskID = t.TaskID
            JOIN Students s ON st.StudentID = s.StudentID
            JOIN Subjects sub ON t.SubjectID = sub.SubjectID
            JOIN Classes c ON t.ClassID = c.ClassID
            WHERE t.TeacherID = ? AND st.Status = 'submitted'
            ORDER BY s.LastName, s.FirstName, t.Date DESC
        ''', (teacher_id,))

        tasks = cursor.fetchall()

        if not tasks:
            return []

        return [
            f"<b>{task['LastName']} {task['FirstName']}</b> - {task['SubjectTitle']} {task['Topic']} ({task['ClassTitle']})"
            for task in tasks
        ]


def get_class_grades(class_name: str, teacher_login: str) -> list[str] | bool:
    """Получает статистику оценок по конкретному классу"""
    teacher_id = get_teacher_id_by_login(teacher_login)
    if not teacher_id:
        return False

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Проверяем доступ учителя к классу
        cursor.execute('''
            SELECT c.ClassID 
            FROM Classes c
            LEFT JOIN MyClasses mc ON c.ClassID = mc.ClassID AND mc.TeacherID = ?
            LEFT JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
            LEFT JOIN TeachersInSchools tis ON cis.SchoolID = tis.SchoolID AND tis.TeacherID = ?
            WHERE c.ClassTitle = ? AND (mc.TeacherID IS NOT NULL OR tis.TeacherID IS NOT NULL)
        ''', (teacher_id, teacher_id, class_name))

        class_info = cursor.fetchone()
        if not class_info:
            return False

        class_id = class_info['ClassID']

        # 2. Получаем статистику только по заданиям этого класса
        cursor.execute('''
            SELECT 
                s.StudentID,
                s.LastName || ' ' || s.FirstName AS student_name,
                COUNT(CASE WHEN st.Status = 'graded' AND t.ClassID = ? THEN 1 END) AS graded_count,
                COUNT(CASE WHEN st.Status = 'failed' AND t.ClassID = ? THEN 1 END) AS failed_count,
                COUNT(CASE WHEN st.Status = 'submitted' AND t.ClassID = ? THEN 1 END) AS submitted_count,
                AVG(CASE WHEN st.Mark IN ('2','3','4','5') AND t.ClassID = ? THEN CAST(st.Mark AS REAL) ELSE NULL END) AS avg_grade
            FROM Students s
            JOIN StudentInClasses sc ON s.StudentID = sc.StudentID AND sc.ClassID = ?
            LEFT JOIN StudentTasks st ON s.StudentID = st.StudentID
            LEFT JOIN Tasks t ON st.TaskID = t.TaskID AND t.ClassID = ?
            GROUP BY s.StudentID
            ORDER BY s.LastName, s.FirstName
        ''', (class_id, class_id, class_id, class_id, class_id, class_id))

        stats = cursor.fetchall()

        if not stats:
            return [f"В классе {class_name} пока нет оценок"]

        result = [f"<b>Ведомость оценок класса {class_name}:</b>"]
        for stat in stats:
            result.append(
                f"<b>{stat['student_name']}</b>:\n"
                f"Оценки - {stat['graded_count']}, "
                f"Незачеты - {stat['failed_count']}, "
                f"На проверке - {stat['submitted_count']}, "
                f"Средний балл - {round(stat['avg_grade'], 2) if stat['avg_grade'] else 'нет'}"
            )

        return result


def get_new_tasks(student_login: str) -> list[str]:
    student_id = get_student_id_by_login(student_login)
    if not student_id:
        return []

    tasks = get_student_tasks(student_id)
    return [
        f"<b>{task['subject']}</b> - {task['theme']} (до {task['deadline']})"
        for task in tasks
        if task['status'] == 'not_submitted' and not is_deadline_passed(task['deadline_unix'])
    ]


def get_assessed_tasks(student_login: str) -> list[str]:
    student_id = get_student_id_by_login(student_login)
    if not student_id:
        return []

    tasks = get_student_tasks(student_id)
    return [
        f"<b>{task['subject']}</b> - {task['theme']}: {task['grade']} ({task['comment'] or 'без комментария'})"
        for task in tasks
        if task['status'] == 'graded'
    ]


def get_grades(student_login: str) -> dict[str, str]:
    student_id = get_student_id_by_login(student_login)
    if not student_id:
        return {}

    tasks = get_student_tasks(student_id)
    return {
        f"<b>{task['subject']}</b> - {task['theme']}": task['grade']
        for task in tasks
        if task['grade']
    }


def is_deadline_passed(deadline_unix):
    """Вспомогательная функция для проверки дедлайна"""
    from datetime import datetime
    if not deadline_unix:
        return False
    deadline_date = datetime.fromtimestamp(int(deadline_unix))
    return datetime.now() > deadline_date